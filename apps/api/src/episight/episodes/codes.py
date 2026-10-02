"""Display labels for codes used in the prototype corpus. Unknown codes return None (label is optional)."""

ICD10_LABELS: dict[str, str] = {
    "I50.0": "Congestive heart failure",
    "I25.1": "Atherosclerotic heart disease",
    "J18.9": "Pneumonia, unspecified",
    "N39.0": "Urinary tract infection, site not specified",
    "K29.7": "Gastritis, unspecified",
    "E11.9": "Type 2 diabetes mellitus without complications",
    "I10": "Essential (primary) hypertension",
    "J44.1": "COPD with acute exacerbation",
    "A09": "Gastroenteritis and colitis of unspecified origin",
}

ICD9CM_LABELS: dict[str, str] = {
    "88.56": "Coronary arteriography using two catheters",
    "36.06": "Insertion of non-drug-eluting coronary artery stent(s)",
    "36.07": "Insertion of drug-eluting coronary artery stent(s)",
    "89.52": "Electrocardiogram",
    "87.44": "Routine chest x-ray",
}


def diagnosis_label(code: str) -> str | None:
    return ICD10_LABELS.get(code)


def procedure_label(code: str) -> str | None:
    return ICD9CM_LABELS.get(code)
