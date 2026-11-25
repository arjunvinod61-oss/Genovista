import re

RSID_RE = re.compile(r"^rs[0-9]+$", re.IGNORECASE)
GENE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]{0,19}$")
CLINVAR_RE = re.compile(r"^(?:VCV|RCV)[0-9]+(?:\.[0-9]+)?$", re.IGNORECASE)


def normalize_rsid(value: str) -> str:
    value = (value or "").strip()
    if not RSID_RE.fullmatch(value):
        raise ValueError("Enter an rsID such as rs7412.")
    return "rs" + value[2:]


def normalize_gene_symbol(value: str) -> str:
    value = (value or "").strip().upper()
    if not GENE_RE.fullmatch(value):
        raise ValueError("Enter a valid gene symbol, such as BRCA1 or TP53.")
    return value


def normalize_clinvar_accession(value: str) -> str:
    value = (value or "").strip().upper()
    if not CLINVAR_RE.fullmatch(value):
        raise ValueError("Enter a ClinVar accession such as VCV000014206 or RCV000001.")
    return value
