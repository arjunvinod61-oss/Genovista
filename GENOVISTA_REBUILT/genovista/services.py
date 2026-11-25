"""Thin, explicit clients for NCBI Variation, NCBI E-utilities and Ensembl REST."""
from __future__ import annotations
import os, re, time
from typing import Any
import requests

TIMEOUT = 25
USER_AGENT = "GENOVISTA/2.0 (educational bioinformatics application)"


class APIError(RuntimeError):
    pass


class HTTPClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def get_json(self, url: str, params: dict | None = None, headers: dict | None = None):
        last = None
        for attempt in range(3):
            try:
                response = self.session.get(url, params=params, headers=headers, timeout=TIMEOUT)
                if response.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                response.raise_for_status()
                return response.json()
            except (requests.RequestException, ValueError) as exc:
                last = exc
                if attempt < 2:
                    time.sleep(0.6 * (attempt + 1))
        raise APIError(f"Request failed for {url}: {last}")


class EnsemblClient(HTTPClient):
    base = "https://rest.ensembl.org"

    def lookup_gene(self, symbol: str) -> dict:
        data = self.get_json(f"{self.base}/lookup/symbol/homo_sapiens/{symbol}",
                             params={"expand": 0}, headers={"Accept": "application/json"})
        return {
            "gene_symbol": data.get("display_name") or symbol,
            "ensembl_gene_id": data.get("id"),
            "chromosome": str(data.get("seq_region_name", "")),
            "start": data.get("start"), "end": data.get("end"),
            "strand": data.get("strand"),
            "assembly": data.get("assembly_name"),
            "description": data.get("description"),
            "source": "Ensembl REST",
            "raw_data": data,
        }

    def variant_effect(self, rsid: str) -> list[dict]:
        data = self.get_json(f"{self.base}/vep/human/id/{rsid}",
                             headers={"Accept": "application/json"})
        if isinstance(data, dict):
            data = [data]
        return data if isinstance(data, list) else []


class DbSNPClient(HTTPClient):
    base = "https://api.ncbi.nlm.nih.gov/variation/v0"

    def get_ref_snp(self, rsid: str) -> dict:
        numeric_id = re.sub(r"^rs", "", rsid, flags=re.I)
        data = self.get_json(f"{self.base}/refsnp/{numeric_id}")
        if not isinstance(data, dict) or "refsnp_id" not in data:
            raise APIError(f"NCBI returned an unexpected RefSNP response for {rsid}.")
        return data

    @staticmethod
    def summarize(data: dict, preferred_assembly: str = "GRCh38") -> dict:
        """Extract a best-effort placement summary without inventing coordinates."""
        result = {"chromosome": None, "position": None, "ref_allele": None,
                  "alt_allele": None, "assembly": None, "gene_symbol": None}
        snapshot = data.get("primary_snapshot_data", {})
        placements = snapshot.get("placements_with_allele", [])
        # Prefer the requested assembly across all placements before falling back.
        ordered = []
        for placement in placements:
            traits = placement.get("placement_annot", {}).get("seq_id_traits_by_assembly", [])
            if any(str(x.get("assembly_name", "")).startswith(preferred_assembly) for x in traits):
                ordered.insert(0, placement)
            else:
                ordered.append(placement)
        for placement in ordered:
            annot = placement.get("placement_annot", {})
            traits = annot.get("seq_id_traits_by_assembly", [])
            chosen = next((x for x in traits if str(x.get("assembly_name", "")).startswith(preferred_assembly)), None)
            chosen = chosen or (traits[0] if traits else {})
            if not chosen:
                continue
            seq_id = chosen.get("seq_id")
            result["assembly"] = chosen.get("assembly_name")
            result["chromosome"] = chosen.get("chromosome")
            for allele in placement.get("alleles", []):
                spdi = allele.get("allele", {}).get("spdi", {})
                if spdi.get("seq_id") == seq_id:
                    # SPDI positions are zero-based; convert to 1-based display coordinates.
                    spdi_position = spdi.get("position")
                    result["position"] = (spdi_position + 1) if isinstance(spdi_position, int) else None
                    result["ref_allele"] = spdi.get("deleted_sequence")
                    result["alt_allele"] = spdi.get("inserted_sequence")
                    break
            if result["position"] is not None:
                break
        return result


class ClinVarClient(HTTPClient):
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def search_by_term(self, term: str, retmax: int = 10) -> list[dict]:
        api_key = os.getenv("NCBI_API_KEY")
        params = {"db": "clinvar", "term": term, "retmode": "json", "retmax": retmax,
                  "tool": "genovista", "email": os.getenv("NCBI_EMAIL", "")}
        if api_key:
            params["api_key"] = api_key
        search = self.get_json(f"{self.base}/esearch.fcgi", params=params)
        ids = search.get("esearchresult", {}).get("idlist", [])
        if not ids:
            return []
        summary_params = {"db": "clinvar", "id": ",".join(ids), "retmode": "json",
                          "tool": "genovista", "email": os.getenv("NCBI_EMAIL", "")}
        if api_key:
            summary_params["api_key"] = api_key
        summary = self.get_json(f"{self.base}/esummary.fcgi", params=summary_params)
        result = summary.get("result", {})
        return [result[i] for i in ids if i in result]

    def search_accession(self, accession: str) -> list[dict]:
        # ClinVar ESearch accepts accession strings as search terms; returned UIDs
        # are then passed to ESummary (not the VCV/RCV string itself).
        return self.search_by_term(f'"{accession}"', retmax=10)
