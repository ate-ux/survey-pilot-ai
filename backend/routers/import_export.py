"""Module Import/Export - CSV, Excel, PDF, Word."""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional
import io
import csv
import json

from database import get_db
from auth import require_user
import models

# Librairies
try:
    import pandas as pd
except ImportError:
    pd = None

try:
    from docx import Document
except ImportError:
    Document = None

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

router = APIRouter(prefix="/api/io", tags=["import-export"])


def _log_audit(db, user_id, action, entity_type=None, entity_id=None, details=None):
    db.add(models.AuditLog(
        user_id=user_id, action=action,
        entity_type=entity_type, entity_id=entity_id,
        details=details,
    ))
    db.commit()


# ============================================================
# 1. IMPORT - Réponses depuis CSV
# ============================================================
@router.post("/import/responses/csv")
async def import_responses_csv(
    survey_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    """
    Import CSV de réponses.
    Format : 1ère ligne = codes des questions (age,genre,satisfaction)
    """
    survey = db.query(models.Survey).filter(models.Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Enquête introuvable")

    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    headers = reader.fieldnames or []

    questions = db.query(models.Question).filter(models.Question.survey_id == survey_id).all()
    code_to_qid = {q.code: q.id for q in questions}

    missing = [h for h in headers if h not in code_to_qid]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Colonnes inconnues : {missing}. Codes dispo : {list(code_to_qid.keys())}"
        )

    imported = 0
    for idx, row in enumerate(reader, start=1):
        response = models.Response(
            survey_id=survey_id,
            respondent_code=f"CSV-{idx}",
            environment_id=1,
        )
        db.add(response)
        db.flush()
        for code, value in row.items():
            if value and code in code_to_qid:
                db.add(models.Answer(
                    response_id=response.id,
                    question_id=code_to_qid[code],
                    value=str(value),
                ))
        imported += 1

    db.commit()
    _log_audit(db, user.id, "io.import.csv", "survey", survey_id, {"count": imported})
    return {"status": "imported", "count": imported, "survey_id": survey_id}


# ============================================================
# 2. IMPORT - Réponses depuis Excel
# ============================================================
@router.post("/import/responses/excel")
async def import_responses_excel(
    survey_id: int = Form(...),
    sheet_name: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    """Import Excel (.xlsx) de réponses. 1ère ligne = codes questions."""
    if pd is None:
        raise HTTPException(status_code=500, detail="pandas non installé")

    survey = db.query(models.Survey).filter(models.Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Enquête introuvable")

    content = await file.read()
    try:
        df = pd.read_excel(io.BytesIO(content), sheet_name=sheet_name or 0)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lecture Excel : {e}")

    questions = db.query(models.Question).filter(models.Question.survey_id == survey_id).all()
    code_to_qid = {q.code: q.id for q in questions}

    missing = [c for c in df.columns if c not in code_to_qid]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Colonnes inconnues : {missing}. Codes dispo : {list(code_to_qid.keys())}"
        )

    imported = 0
    for idx, row in df.iterrows():
        response = models.Response(
            survey_id=survey_id,
            respondent_code=f"XLS-{idx+1}",
            environment_id=1,
        )
        db.add(response)
        db.flush()
        for code in df.columns:
            value = row[code]
            if pd.notna(value) and code in code_to_qid:
                db.add(models.Answer(
                    response_id=response.id,
                    question_id=code_to_qid[code],
                    value=str(value),
                ))
        imported += 1

    db.commit()
    _log_audit(db, user.id, "io.import.excel", "survey", survey_id, {"count": imported})
    return {"status": "imported", "count": imported, "survey_id": survey_id}


# ============================================================
# 3. IMPORT - Questions depuis Excel
# ============================================================
@router.post("/import/questions/excel")
async def import_questions_excel(
    survey_id: int = Form(...),
    sheet_name: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    """
    Import Excel de questions.
    Colonnes attendues : code, label, question_type, options (optionnel)
    """
    if pd is None:
        raise HTTPException(status_code=500, detail="pandas non installé")

    survey = db.query(models.Survey).filter(models.Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Enquête introuvable")

    content = await file.read()
    try:
        df = pd.read_excel(io.BytesIO(content), sheet_name=sheet_name or 0)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lecture Excel : {e}")

    required_cols = {"code", "label", "question_type"}
    if not required_cols.issubset(set(df.columns)):
        raise HTTPException(
            status_code=400,
            detail=f"Colonnes obligatoires : {required_cols}. Reçues : {list(df.columns)}"
        )

    # Récupérer le prochain order_index
    max_order = db.query(models.Question).filter(
        models.Question.survey_id == survey_id
    ).count()

    created = 0
    for idx, row in df.iterrows():
        code = str(row["code"]).strip()
        # Vérifier doublon
        exists = db.query(models.Question).filter(
            models.Question.survey_id == survey_id,
            models.Question.code == code,
        ).first()
        if exists:
            continue

        options = None
        if "options" in df.columns and pd.notna(row["options"]):
            try:
                options = json.loads(str(row["options"]))
            except Exception:
                options = str(row["options"]).split(",")

        db.add(models.Question(
            survey_id=survey_id,
            order_index=max_order + created + 1,
            code=code,
            label=str(row["label"]),
            question_type=str(row["question_type"]),
            options=options,
            is_required=True,
        ))
        created += 1

    db.commit()
    _log_audit(db, user.id, "io.import.questions.excel", "survey", survey_id,
               {"count": created})
    return {"status": "imported", "count": created, "survey_id": survey_id}


# ============================================================
# 4. IMPORT - Questions depuis Word (.docx)
# ============================================================
@router.post("/import/questions/word")
async def import_questions_word(
    survey_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    """
    Import Word de questions.
    Format attendu : paragraphes numérotés
    Ex: "1. Quel âge avez-vous ?"
        "2. Genre ? (M/F)"
    """
    if Document is None:
        raise HTTPException(status_code=500, detail="python-docx non installé")

    survey = db.query(models.Survey).filter(models.Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Enquête introuvable")

    content = await file.read()
    try:
        doc = Document(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lecture Word : {e}")

    max_order = db.query(models.Question).filter(
        models.Question.survey_id == survey_id
    ).count()

    created = 0
    import re
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        # Détecter "1. Question" ou "1) Question"
        match = re.match(r"^(\d+)[\.\)]\s*(.+)$", text)
        if not match:
            continue

        label = match.group(2).strip()
        code = f"Q{max_order + created + 1:03d}"

        # Détecter type : si contient (M/F), (oui/non) -> select
        question_type = "text"
        options = None
        if re.search(r"\(.*[/|,].*\)", label):
            question_type = "select"
            opts_match = re.search(r"\(([^)]+)\)", label)
            if opts_match:
                options = [o.strip() for o in opts_match.group(1).split("/")]

        db.add(models.Question(
            survey_id=survey_id,
            order_index=max_order + created + 1,
            code=code,
            label=label,
            question_type=question_type,
            options=options,
            is_required=True,
        ))
        created += 1

    db.commit()
    _log_audit(db, user.id, "io.import.questions.word", "survey", survey_id,
               {"count": created})
    return {"status": "imported", "count": created, "survey_id": survey_id}


# ============================================================
# 5. IMPORT - Questions depuis PDF
# ============================================================
@router.post("/import/questions/pdf")
async def import_questions_pdf(
    survey_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    """Import PDF de questions (extraction de texte + parsing)."""
    if PdfReader is None:
        raise HTTPException(status_code=500, detail="pypdf non installé")

    survey = db.query(models.Survey).filter(models.Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Enquête introuvable")

    content = await file.read()
    try:
        reader = PdfReader(io.BytesIO(content))
        full_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lecture PDF : {e}")

    max_order = db.query(models.Question).filter(
        models.Question.survey_id == survey_id
    ).count()

    created = 0
    import re
    for line in full_text.split("\n"):
        text = line.strip()
        if not text:
            continue

        match = re.match(r"^(\d+)[\.\)]\s*(.+)$", text)
        if not match:
            continue

        label = match.group(2).strip()
        code = f"Q{max_order + created + 1:03d}"

        db.add(models.Question(
            survey_id=survey_id,
            order_index=max_order + created + 1,
            code=code,
            label=label,
            question_type="text",
            is_required=True,
        ))
        created += 1

    db.commit()
    _log_audit(db, user.id, "io.import.questions.pdf", "survey", survey_id,
               {"count": created})
    return {"status": "imported", "count": created, "survey_id": survey_id}


# ============================================================
# 6. Télécharger un modèle CSV de réponses
# ============================================================
@router.get("/template/responses/{survey_id}")
def download_csv_template(
    survey_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    """Génère un CSV vide avec les colonnes = codes des questions."""
    questions = db.query(models.Question).filter(
        models.Question.survey_id == survey_id
    ).order_by(models.Question.order_index).all()

    if not questions:
        raise HTTPException(status_code=400, detail="Aucune question dans cette enquête")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([q.code for q in questions])
    writer.writerow(["exemple1"] * len(questions))

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=template_survey_{survey_id}.csv"}
    )


# ============================================================
# 7. Télécharger un modèle Excel de questions
# ============================================================
@router.get("/template/questions")
def download_excel_template(user: models.User = Depends(require_user)):
    """Génère un Excel vide pour importer des questions."""
    if pd is None:
        raise HTTPException(status_code=500, detail="pandas non installé")

    df = pd.DataFrame([
        {"code": "age", "label": "Quel âge avez-vous ?", "question_type": "number", "options": ""},
        {"code": "genre", "label": "Genre ?", "question_type": "select", "options": '["M","F"]'},
        {"code": "satisfaction", "label": "Satisfaction (1-5)", "question_type": "number", "options": ""},
    ])

    output = io.BytesIO()
    df.to_excel(output, index=False, engine="openpyxl")
    output.seek(0)

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=template_questions.xlsx"}
    )


# ============================================================
# BLOC B - EXPORT & RAPPORTS
# ============================================================

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
)
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY


# ============================================================
# 8. EXPORT - Réponses en CSV
# ============================================================
@router.get("/export/responses/csv/{survey_id}")
def export_responses_csv(
    survey_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    survey = db.query(models.Survey).filter(models.Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Enquête introuvable")

    questions = db.query(models.Question).filter(
        models.Question.survey_id == survey_id
    ).order_by(models.Question.order_index).all()
    q_codes = [q.code for q in questions]
    q_ids = [q.id for q in questions]

    responses = db.query(models.Response).filter(
        models.Response.survey_id == survey_id
    ).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["response_id", "respondent_code", "collected_at"] + q_codes)

    for r in responses:
        answers = db.query(models.Answer).filter(
            models.Answer.response_id == r.id
        ).all()
        ans_map = {a.question_id: a.value for a in answers}
        row = [
            r.id,
            r.respondent_code or "",
            r.collected_at.isoformat() if r.collected_at else "",
        ] + [ans_map.get(qid, "") for qid in q_ids]
        writer.writerow(row)

    output.seek(0)
    _log_audit(db, user.id, "io.export.csv", "survey", survey_id, {"count": len(responses)})

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=responses_survey_{survey_id}.csv"}
    )


# ============================================================
# 9. EXPORT - Réponses en Excel
# ============================================================
@router.get("/export/responses/excel/{survey_id}")
def export_responses_excel(
    survey_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    if pd is None:
        raise HTTPException(status_code=500, detail="pandas non installé")

    survey = db.query(models.Survey).filter(models.Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Enquête introuvable")

    questions = db.query(models.Question).filter(
        models.Question.survey_id == survey_id
    ).order_by(models.Question.order_index).all()
    q_codes = [q.code for q in questions]
    q_ids = [q.id for q in questions]

    responses = db.query(models.Response).filter(
        models.Response.survey_id == survey_id
    ).all()

    rows = []
    for r in responses:
        answers = db.query(models.Answer).filter(
            models.Answer.response_id == r.id
        ).all()
        ans_map = {a.question_id: a.value for a in answers}
        row = {
            "response_id": r.id,
            "respondent_code": r.respondent_code or "",
            "collected_at": r.collected_at.isoformat() if r.collected_at else "",
        }
        for code, qid in zip(q_codes, q_ids):
            row[code] = ans_map.get(qid, "")
        rows.append(row)

    df = pd.DataFrame(rows)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Reponses", index=False)

    output.seek(0)
    _log_audit(db, user.id, "io.export.excel", "survey", survey_id, {"count": len(rows)})

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=responses_survey_{survey_id}.xlsx"}
    )


# ============================================================
# 10. EXPORT - Questionnaire en Word
# ============================================================
@router.get("/export/questions/word/{survey_id}")
def export_questions_word(
    survey_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    if Document is None:
        raise HTTPException(status_code=500, detail="python-docx non installé")

    survey = db.query(models.Survey).filter(models.Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Enquête introuvable")

    questions = db.query(models.Question).filter(
        models.Question.survey_id == survey_id
    ).order_by(models.Question.order_index).all()

    doc = Document()
    doc.add_heading(f"Questionnaire : {survey.title}", level=0)
    doc.add_paragraph(f"Code : {survey.code}")
    doc.add_paragraph(f"Description : {survey.description or '—'}")
    doc.add_paragraph("")

    for i, q in enumerate(questions, start=1):
        p = doc.add_paragraph()
        p.add_run(f"{i}. {q.label}").bold = True
        if q.question_type == "select" and q.options:
            opts = q.options if isinstance(q.options, list) else []
            for opt in opts:
                doc.add_paragraph(f"    ☐ {opt}")
        else:
            doc.add_paragraph("    " + "_" * 50)
        doc.add_paragraph("")

    output = io.BytesIO()
    doc.save(output)
    output.seek(0)
    _log_audit(db, user.id, "io.export.questions.word", "survey", survey_id, {})

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename=questionnaire_{survey_id}.docx"}
    )


# ============================================================
# 11. EXPORT - Questionnaire PDF (vierge, imprimable)
# ============================================================
@router.get("/export/questions/pdf/{survey_id}")
def export_questions_pdf(
    survey_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    survey = db.query(models.Survey).filter(models.Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Enquête introuvable")

    questions = db.query(models.Question).filter(
        models.Question.survey_id == survey_id
    ).order_by(models.Question.order_index).all()

    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4,
                            topMargin=2*cm, bottomMargin=2*cm,
                            leftMargin=2*cm, rightMargin=2*cm)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph(f"<b>Questionnaire : {survey.title}</b>",
                           styles["Title"]))
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph(f"Code : {survey.code}", styles["Normal"]))
    story.append(Paragraph(f"Description : {survey.description or '—'}",
                           styles["Normal"]))
    story.append(Spacer(1, 1*cm))

    for i, q in enumerate(questions, start=1):
        story.append(Paragraph(f"<b>{i}. {q.label}</b>", styles["Normal"]))
        if q.question_type == "select" and q.options:
            opts = q.options if isinstance(q.options, list) else []
            for opt in opts:
                story.append(Paragraph(f"&nbsp;&nbsp;&nbsp;☐ {opt}", styles["Normal"]))
        else:
            story.append(Paragraph("&nbsp;&nbsp;&nbsp;" + "_" * 50,
                                   styles["Normal"]))
        story.append(Spacer(1, 0.4*cm))

    doc.build(story)
    output.seek(0)
    _log_audit(db, user.id, "io.export.questions.pdf", "survey", survey_id, {})

    return StreamingResponse(
        output,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=questionnaire_{survey_id}.pdf"}
    )


# ============================================================
# 12. RAPPORT PDF professionnel
# ============================================================
@router.get("/report/pdf/{survey_id}")
def generate_report_pdf(
    survey_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    """
    Génère un rapport d'analyse PDF professionnel :
    page de garde, sommaire, statistiques, conclusion.
    """
    survey = db.query(models.Survey).filter(models.Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Enquête introuvable")

    questions = db.query(models.Question).filter(
        models.Question.survey_id == survey_id
    ).order_by(models.Question.order_index).all()

    responses = db.query(models.Response).filter(
        models.Response.survey_id == survey_id
    ).all()

    # Stats par question
    stats_data = []
    for q in questions:
        answers = (
            db.query(models.Answer)
            .join(models.Response, models.Response.id == models.Answer.response_id)
            .filter(models.Response.survey_id == survey_id)
            .filter(models.Answer.question_id == q.id)
            .all()
        )
        values = [a.value for a in answers if a.value]
        numeric = []
        for v in values:
            try:
                numeric.append(float(v))
            except (ValueError, TypeError):
                pass

        stat = {
            "code": q.code,
            "label": q.label,
            "n_answered": len(values),
            "fill_rate": round(len(values) / len(responses) * 100, 1) if responses else 0,
        }
        if len(numeric) >= len(values) * 0.7 and numeric:
            import numpy as np
            arr = np.array(numeric)
            stat["mean"] = round(float(arr.mean()), 2)
            stat["std"] = round(float(arr.std(ddof=1)) if len(arr) > 1 else 0, 2)
            stat["min"] = round(float(arr.min()), 2)
            stat["max"] = round(float(arr.max()), 2)
        stats_data.append(stat)

    # ====== Génération PDF ======
    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4,
                            topMargin=2*cm, bottomMargin=2*cm,
                            leftMargin=2*cm, rightMargin=2*cm)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle("TitleCustom", parent=styles["Title"],
                                  fontSize=24, textColor=colors.HexColor("#1a237e"),
                                  alignment=TA_CENTER, spaceAfter=20)
    h1 = ParagraphStyle("H1", parent=styles["Heading1"],
                        fontSize=16, textColor=colors.HexColor("#1a237e"),
                        spaceAfter=10, spaceBefore=15)
    h2 = ParagraphStyle("H2", parent=styles["Heading2"],
                        fontSize=13, textColor=colors.HexColor("#283593"),
                        spaceAfter=8, spaceBefore=10)
    body = ParagraphStyle("Body", parent=styles["Normal"],
                          fontSize=10, alignment=TA_JUSTIFY, spaceAfter=6)

    story = []

    # --- PAGE DE GARDE ---
    story.append(Spacer(1, 4*cm))
    story.append(Paragraph("<b>SurveyPilot AI V2</b>", title_style))
    story.append(Spacer(1, 1*cm))
    story.append(Paragraph(f"<b>Rapport d'analyse</b>", title_style))
    story.append(Spacer(1, 2*cm))
    story.append(Paragraph(f"<b>{survey.title}</b>",
                           ParagraphStyle("c", parent=body, fontSize=14, alignment=TA_CENTER)))
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph(f"Code : {survey.code}",
                           ParagraphStyle("c2", parent=body, alignment=TA_CENTER)))
    story.append(Paragraph(f"Généré le : {__import__('datetime').datetime.now().strftime('%d/%m/%Y %H:%M')}",
                           ParagraphStyle("c3", parent=body, alignment=TA_CENTER)))
    story.append(PageBreak())

    # --- SOMMAIRE ---
    story.append(Paragraph("Sommaire", h1))
    story.append(Paragraph("1. Informations générales", body))
    story.append(Paragraph("2. Statistiques descriptives", body))
    story.append(Paragraph("3. Conclusion et recommandations", body))
    story.append(PageBreak())

    # --- 1. INFORMATIONS GÉNÉRALES ---
    story.append(Paragraph("1. Informations générales", h1))
    info_data = [
        ["Champ", "Valeur"],
        ["Titre de l'enquête", survey.title],
        ["Code", survey.code],
        ["Statut", survey.status],
        ["Population cible", str(survey.target_population or "—")],
        ["Taille d'échantillon", str(survey.sample_size or "—")],
        ["Nombre de questions", str(len(questions))],
        ["Nombre de réponses collectées", str(len(responses))],
        ["Taux de remplissage moyen",
         f"{round(sum(s['fill_rate'] for s in stats_data) / len(stats_data), 1) if stats_data else 0} %"],
    ]
    table = Table(info_data, colWidths=[7*cm, 9*cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a237e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
    ]))
    story.append(table)
    story.append(PageBreak())

    # --- 2. STATISTIQUES DESCRIPTIVES ---
    story.append(Paragraph("2. Statistiques descriptives", h1))

    for i, s in enumerate(stats_data, start=1):
        story.append(Paragraph(f"2.{i}. {s['label']} ({s['code']})", h2))
        story.append(Paragraph(
            f"Réponses : <b>{s['n_answered']}</b> · Taux de remplissage : <b>{s['fill_rate']}%</b>",
            body
        ))
        if "mean" in s:
            row = [
                ["Moyenne", "Écart-type", "Min", "Max"],
                [str(s["mean"]), str(s["std"]), str(s["min"]), str(s["max"])],
            ]
            t = Table(row, colWidths=[4*cm, 4*cm, 4*cm, 4*cm])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#283593")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ]))
            story.append(t)
        story.append(Spacer(1, 0.3*cm))

    story.append(PageBreak())

    # --- 3. CONCLUSION ---
    story.append(Paragraph("3. Conclusion et recommandations", h1))
    conclusion = f"""
    Cette enquête <b>{survey.title}</b> a permis de collecter <b>{len(responses)}</b> réponses
    sur les <b>{len(questions)}</b> questions posées. Le taux de remplissage moyen est de
    <b>{round(sum(s['fill_rate'] for s in stats_data) / len(stats_data), 1) if stats_data else 0}%</b>.
    <br/><br/>
    Recommandations générales :
    <br/>• Vérifier les questions à faible taux de remplissage (&lt; 80%).
    <br/>• Analyser les valeurs extrêmes détectées par le module ML.
    <br/>• Compléter la collecte si le nombre de réponses est inférieur à l'échantillon cible.
    <br/>• Utiliser les modules d'analyse statistique pour approfondir les corrélations.
    """
    story.append(Paragraph(conclusion, body))

    doc.build(story)
    output.seek(0)
    _log_audit(db, user.id, "io.report.pdf", "survey", survey_id, {})

    return StreamingResponse(
        output,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=rapport_survey_{survey_id}.pdf"}
    )


# ============================================================
# 13. RAPPORT Word professionnel
# ============================================================
@router.get("/report/word/{survey_id}")
def generate_report_word(
    survey_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_user),
):
    if Document is None:
        raise HTTPException(status_code=500, detail="python-docx non installé")

    survey = db.query(models.Survey).filter(models.Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Enquête introuvable")

    questions = db.query(models.Question).filter(
        models.Question.survey_id == survey_id
    ).order_by(models.Question.order_index).all()

    responses = db.query(models.Response).filter(
        models.Response.survey_id == survey_id
    ).all()

    doc = Document()

    # Page de garde
    doc.add_heading("SurveyPilot AI V2", 0)
    doc.add_heading("Rapport d'analyse", level=1)
    doc.add_paragraph("")
    doc.add_paragraph(f"Enquête : {survey.title}").bold = True
    doc.add_paragraph(f"Code : {survey.code}")
    doc.add_paragraph(f"Date : {__import__('datetime').datetime.now().strftime('%d/%m/%Y %H:%M')}")
    doc.add_page_break()

    # 1. Infos générales
    doc.add_heading("1. Informations générales", level=1)
    doc.add_paragraph(f"Titre : {survey.title}")
    doc.add_paragraph(f"Code : {survey.code}")
    doc.add_paragraph(f"Population cible : {survey.target_population or '—'}")
    doc.add_paragraph(f"Taille d'échantillon : {survey.sample_size or '—'}")
    doc.add_paragraph(f"Nombre de questions : {len(questions)}")
    doc.add_paragraph(f"Nombre de réponses collectées : {len(responses)}")
    doc.add_page_break()

    # 2. Statistiques par question
    doc.add_heading("2. Statistiques descriptives", level=1)

    for i, q in enumerate(questions, start=1):
        answers = (
            db.query(models.Answer)
            .join(models.Response, models.Response.id == models.Answer.response_id)
            .filter(models.Response.survey_id == survey_id)
            .filter(models.Answer.question_id == q.id)
            .all()
        )
        values = [a.value for a in answers if a.value]
        numeric = []
        for v in values:
            try:
                numeric.append(float(v))
            except (ValueError, TypeError):
                pass

        doc.add_heading(f"2.{i}. {q.label} ({q.code})", level=2)
        doc.add_paragraph(f"Réponses : {len(values)}")

        if len(numeric) >= len(values) * 0.7 and numeric:
            import numpy as np
            arr = np.array(numeric)
            table = doc.add_table(rows=2, cols=4)
            table.style = "Light Grid Accent 1"
            headers = ["Moyenne", "Écart-type", "Min", "Max"]
            data = [
                round(float(arr.mean()), 2),
                round(float(arr.std(ddof=1)) if len(arr) > 1 else 0, 2),
                round(float(arr.min()), 2),
                round(float(arr.max()), 2),
            ]
            for j, h in enumerate(headers):
                table.cell(0, j).text = h
                table.cell(1, j).text = str(data[j])
        doc.add_paragraph("")

    doc.add_page_break()

    # 3. Conclusion
    doc.add_heading("3. Conclusion", level=1)
    doc.add_paragraph(
        f"Cette enquête a permis de collecter {len(responses)} réponses sur "
        f"{len(questions)} questions. Les statistiques descriptives sont présentées ci-dessus. "
        f"Pour approfondir, utilisez le module d'analyse statistique et ML de SurveyPilot AI."
    )

    output = io.BytesIO()
    doc.save(output)
    output.seek(0)
    _log_audit(db, user.id, "io.report.word", "survey", survey_id, {})

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename=rapport_survey_{survey_id}.docx"}
    )