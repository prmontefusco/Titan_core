"""Adapter de infraestrutura para geração de PDF do Dossier usando ReportLab (Passo 7.8)."""

import hashlib
import io
from datetime import UTC, datetime
from typing import Any

from reportlab.lib import colors  # type: ignore[import-untyped]
from reportlab.lib.pagesizes import A4  # type: ignore[import-untyped]
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # type: ignore[import-untyped]
from reportlab.platypus import (  # type: ignore[import-untyped]
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from packages.core_domain.crypto import CryptographicProfile, KeyIdentifier
from packages.core_domain.dossier import Dossier
from packages.core_domain.dossier_pdf import DossierPdfRepresentation


class SoftwareDossierPdfAdapter:
    """Gera representação PDF determinística e autocontida a partir de um Dossier."""

    def generate_pdf(
        self,
        dossier: Dossier,
        signing_provider: Any | None = None,
        key_id: KeyIdentifier | None = None,
    ) -> DossierPdfRepresentation:
        pdf_bytes = self._build_pdf_bytes(dossier)
        pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()
        now = datetime.now(UTC)

        qr_payload = (
            f"titan://verify?dossier_id={dossier.dossier_id.value}"
            f"&hash={dossier.dossier_hash}"
            f"&pdf_hash={pdf_hash}"
        )

        signature = None
        if signing_provider is not None and key_id is not None:
            signature = signing_provider.sign(
                content_hash=pdf_bytes,
                key_identifier=key_id,
                profile=CryptographicProfile.INSTITUTIONAL_SIGNATURE,
            )

        return DossierPdfRepresentation(
            dossier_id=dossier.dossier_id,
            organization_id=dossier.organization_id,
            pdf_bytes=pdf_bytes,
            pdf_hash=pdf_hash,
            generated_at=now,
            verification_qr_payload=qr_payload,
            signature=signature,
        )

    def _build_pdf_bytes(self, dossier: Dossier) -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=36,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "TitleStyle",
            parent=styles["Heading1"],
            fontSize=16,
            textColor=colors.HexColor("#1A202C"),
            spaceAfter=12,
        )
        subtitle_style = ParagraphStyle(
            "SubTitleStyle",
            parent=styles["Heading2"],
            fontSize=12,
            textColor=colors.HexColor("#2D3748"),
            spaceBefore=10,
            spaceAfter=6,
        )
        normal_style = ParagraphStyle(
            "NormalStyle",
            parent=styles["Normal"],
            fontSize=9,
            textColor=colors.HexColor("#4A5568"),
            leading=12,
        )

        story: list[Any] = []

        # Cabeçalho
        story.append(Paragraph("TITAN CORE — DOSSIÊ DE DECISÃO AUDITÁVEL", title_style))
        story.append(
            Paragraph(
                f"<b>ID do Dossiê:</b> {dossier.dossier_id.value} | "
                f"<b>Organização:</b> {dossier.organization_id.value}",
                normal_style,
            )
        )
        story.append(
            Paragraph(
                f"<b>Finalidade:</b> {dossier.purpose} | "
                f"<b>Gerado em:</b> {dossier.generated_at.isoformat()}",
                normal_style,
            )
        )
        story.append(
            Paragraph(f"<b>Hash Canônico (titan-json-v1):</b> {dossier.dossier_hash}", normal_style)
        )
        story.append(Spacer(1, 12))

        # Seção Decisão
        doc_data = dossier.document
        decision_info = doc_data.get("decision", {})
        story.append(Paragraph("Resumo da Decisão", subtitle_style))
        decision_table_data = [
            ["Item", "Valor"],
            ["ID da Decisão", str(decision_info.get("decision_id"))],
            ["Resultado", str(decision_info.get("result"))],
            ["Emitido em", str(decision_info.get("issued_at"))],
            ["Versão do Motor", str(decision_info.get("engine_version"))],
        ]
        t_decision = Table(decision_table_data, colWidths=[120, 400])
        t_decision.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EDF2F7")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1A202C")),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
                ]
            )
        )
        story.append(t_decision)
        story.append(Spacer(1, 10))

        # Seção Razões da Decisão
        reasons = decision_info.get("reasons", [])
        if reasons:
            story.append(Paragraph("Razões e Motivos da Conclusão", subtitle_style))
            reasons_table_data = [["Código da Razão", "Severidade", "Mensagem Humana"]]
            for r in reasons:
                reasons_table_data.append(
                    [
                        str(r.get("code")),
                        str(r.get("severity")),
                        str(r.get("message")),
                    ]
                )
            t_reasons = Table(reasons_table_data, colWidths=[140, 100, 280])
            t_reasons.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 8),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
                    ]
                )
            )
            story.append(t_reasons)
            story.append(Spacer(1, 10))

        # Seção Política e Avaliação
        eval_info = doc_data.get("evaluation", {})
        policy_info = doc_data.get("policy", {})
        story.append(Paragraph("Política e Avaliação", subtitle_style))
        eval_table_data = [
            ["Item", "Valor"],
            ["ID da Avaliação", str(eval_info.get("evaluation_id"))],
            [
                "Código / Versão da Política",
                f"{policy_info.get('code')} v{policy_info.get('version')}",
            ],
            ["Resultado da Avaliação", str(eval_info.get("outcome"))],
            ["Avaliado em", str(eval_info.get("evaluated_at"))],
        ]
        t_eval = Table(eval_table_data, colWidths=[140, 380])
        t_eval.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EDF2F7")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
                ]
            )
        )
        story.append(t_eval)
        story.append(Spacer(1, 12))

        # Rodapé de integridade
        story.append(
            Paragraph(
                "<i>Este PDF é uma representação derivada autocontida e assinada do Titan Core. "
                "Para validação autônoma sem o servidor, utilize o VerificationBundle JSON.</i>",
                normal_style,
            )
        )

        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes
