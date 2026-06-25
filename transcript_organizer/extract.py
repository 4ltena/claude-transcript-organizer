from .models import Finding

VALID_KINDS = {"design_requirement", "decision", "completed",
               "in_progress", "next_step", "gotcha", "open_question"}

FINDINGS_SCHEMA = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": sorted(VALID_KINDS)},
                    "text": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": ["kind", "text", "confidence"],
            },
        }
    },
    "required": ["findings"],
}

class ExtractionError(Exception):
    pass

def build_prompt(condensed) -> str:
    return (
        "あなたは会話履歴から引き継ぎ用の事実を抽出する分析器です。"
        "以下の凝縮済み会話を読み、既存の設計書に載りにくい会話固有の事実だけを抽出し、"
        "JSON で返してください。kind は "
        f"{sorted(VALID_KINDS)} のいずれか。text は日本語で1-2文、事実のみ。\n\n"
        f"--- 会話: {condensed.title or '(無題)'} ---\n{condensed.body}\n"
    )

def extract(condensed, provider, label: str, retries: int = 2):
    prompt = build_prompt(condensed)
    last_err = None
    for _ in range(retries + 1):
        try:
            data = provider.propose_findings(prompt, FINDINGS_SCHEMA)
            items = data.get("findings", [])
            out = []
            for it in items:
                kind = it.get("kind")
                text = (it.get("text") or "").strip()
                if kind in VALID_KINDS and text:
                    out.append(Finding(
                        kind=kind, text=text,
                        confidence=float(it.get("confidence", 0.0)),
                        source=condensed.title or "(untitled)",
                        src_ts=condensed.last_ts, label=label))
            return out
        except Exception as e:  # provider error or bad json
            last_err = e
    raise ExtractionError(str(last_err))
