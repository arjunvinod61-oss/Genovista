from __future__ import annotations
import csv
import io
import json
import os
from datetime import datetime, timezone

import streamlit as st

from genovista import __version__
from genovista.database import Database
from genovista.services import APIError, ClinVarClient, DbSNPClient, EnsemblClient
from genovista.validators import normalize_rsid, normalize_gene_symbol, normalize_clinvar_accession

st.set_page_config(page_title="GENOVISTA", page_icon="🧬", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
:root { --paper:#F5F2E9; --ink:#25312B; --green:#315C49; --sage:#DDE7DD; --muted:#68756D; --line:#D9D5C9; }
.stApp { background:var(--paper); color:var(--ink); }
[data-testid="stSidebar"] { background:#FFFEFA; border-right:1px solid var(--line); }
h1,h2,h3,h4,p,label,span { color:var(--ink); }
.stButton>button, .stDownloadButton>button { background:var(--green); color:white; border:1px solid var(--green); border-radius:9px; }
.stButton>button:hover, .stDownloadButton>button:hover { background:#244635; color:white; border-color:#244635; }
[data-testid="stMetric"] { background:#FFFEFA; border:1px solid var(--line); padding:14px; border-radius:12px; }
[data-testid="stAlert"] { border-radius:10px; }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def shared_database():
    return Database()


@st.cache_resource
def shared_clients():
    return {"ensembl": EnsemblClient(), "dbsnp": DbSNPClient(), "clinvar": ClinVarClient()}


def initialize_state():
    st.session_state.setdefault("db", shared_database())
    st.session_state.setdefault("clients", shared_clients())
    st.session_state.setdefault("current_variant", None)
    st.session_state.setdefault("current_gene", None)
    st.session_state.setdefault("last_search", None)
    st.session_state.setdefault("search_history", [])
    st.session_state.setdefault("api_errors", [])


def show_header():
    st.title("GENOVISTA 🧬")
    st.caption("Human genetic variant exploration · Evidence from public genomic databases")


def overview():
    db = st.session_state.db
    variants, genes = db.list_variants(), db.list_genes()
    st.subheader("Research overview")
    st.write("Explore human genes and reference variants using live Ensembl and NCBI records. Retrieved records are cached locally with source and retrieval timestamps.")
    a, b, c = st.columns(3)
    a.metric("Saved variant records", len(variants))
    b.metric("Saved gene records", len(genes))
    c.metric("Data sources", "3")
    st.markdown("#### Start exploring")
    st.markdown("- **Gene Explorer:** look up a human gene and inspect its Ensembl coordinates.\n- **Variant Search:** retrieve an rsID from NCBI dbSNP or find ClinVar submissions.\n- **Variant Analysis:** inspect dbSNP record metadata, Ensembl VEP consequences and ClinVar evidence.")
    st.info("GENOVISTA is a research and educational tool. Database assertions are not medical diagnoses.")
    if st.session_state.last_search:
        st.markdown("#### Last retrieved record")
        st.write(st.session_state.last_search)


def gene_explorer():
    st.subheader("Gene Explorer")
    st.write("Look up a human gene using its approved symbol. Example genes: BRCA1, BRCA2, TP53, CFTR, HBB, APOE.")
    with st.form("gene_form"):
        symbol = st.text_input("Gene symbol", placeholder="BRCA1")
        submitted = st.form_submit_button("Retrieve gene", type="primary")
    if submitted:
        try:
            symbol = normalize_gene_symbol(symbol)
            with st.spinner(f"Retrieving {symbol} from Ensembl…"):
                gene = st.session_state.clients["ensembl"].lookup_gene(symbol)
                st.session_state.db.save_gene(gene)
                st.session_state.current_gene = symbol
                st.session_state.last_search = f"Gene {symbol} · Ensembl {gene.get('ensembl_gene_id')}"
        except (ValueError, APIError) as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"Gene lookup failed: {type(exc).__name__}: {exc}")
    selected = st.session_state.current_gene
    if selected:
        gene = st.session_state.db.get_gene(selected)
        if gene:
            st.markdown(f"### 🧬 {gene['gene_symbol']}")
            c1, c2, c3 = st.columns(3)
            c1.metric("Ensembl gene ID", gene.get("ensembl_gene_id") or "Not supplied")
            c2.metric("Chromosome", gene.get("chromosome") or "Not supplied")
            c3.metric("Assembly", gene.get("assembly") or "Not supplied")
            if gene.get("start_position") and gene.get("end_position"):
                st.write(f"**Genomic interval:** {gene['start_position']:,} – {gene['end_position']:,}")
            if gene.get("strand") is not None:
                st.write(f"**Strand:** {'+' if gene['strand'] == 1 else '−'}")
            if gene.get("description"):
                st.write(f"**Description:** {gene['description']}")
            st.caption(f"Source: {gene['source']} · Retrieved: {gene['retrieved_at']}")
            with st.expander("Raw Ensembl response"):
                st.json(gene.get("raw_data", {}))


def _save_dbsnp_record(rsid: str, raw: dict):
    summary = DbSNPClient.summarize(raw)
    st.session_state.db.save_variant(
        variant_id=rsid, source="NCBI dbSNP", record_id=str(raw.get("refsnp_id", "")),
        chromosome=summary.get("chromosome"), position=summary.get("position"),
        ref_allele=summary.get("ref_allele"), alt_allele=summary.get("alt_allele"),
        assembly=summary.get("assembly"), raw_data=raw)
    return summary


def variant_search():
    st.subheader("Variant Search")
    st.write("Retrieve a RefSNP record or search ClinVar for submitted clinical interpretations.")
    search_kind = st.radio("Search type", ["rsID (dbSNP)", "ClinVar accession", "Gene symbol"], horizontal=True)
    with st.form("variant_search_form"):
        term = st.text_input("Identifier", placeholder="rs7412, VCV000014206 or BRCA1")
        submitted = st.form_submit_button("Search public databases", type="primary")
    if submitted:
        try:
            if search_kind == "rsID (dbSNP)":
                rsid = normalize_rsid(term)
                with st.spinner(f"Retrieving {rsid} from NCBI dbSNP…"):
                    raw = st.session_state.clients["dbsnp"].get_ref_snp(rsid)
                    summary = _save_dbsnp_record(rsid, raw)
                st.session_state.current_variant = rsid
                st.session_state.last_search = f"{rsid} · NCBI RefSNP {raw.get('refsnp_id')}"
                st.session_state.search_history.append(st.session_state.last_search)
                st.session_state.last_search_payload = {"kind": "dbSNP", "identifier": rsid, "summary": summary}
            elif search_kind == "ClinVar accession":
                accession = normalize_clinvar_accession(term)
                with st.spinner(f"Searching ClinVar for {accession}…"):
                    records = st.session_state.clients["clinvar"].search_accession(accession)
                if not records:
                    st.warning("NCBI ClinVar returned no matching records for this accession. This is a genuine no-match result, not a successful classification.")
                else:
                    for record in records:
                        st.session_state.db.save_variant(accession, "NCBI ClinVar", record,
                                                         record_id=str(record.get("uid", "")))
                    st.session_state.last_search_payload = {"kind": "ClinVar", "identifier": accession, "records": records}
                    st.session_state.last_search = f"ClinVar {accession} · {len(records)} record(s)"
            else:
                symbol = normalize_gene_symbol(term)
                gene = st.session_state.clients["ensembl"].lookup_gene(symbol)
                st.session_state.db.save_gene(gene)
                st.session_state.current_gene = symbol
                st.session_state.last_search = f"Gene {symbol} · Ensembl {gene.get('ensembl_gene_id')}"
                st.session_state.last_search_payload = {"kind": "Gene", "identifier": symbol}
        except (ValueError, APIError) as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"Search failed: {type(exc).__name__}: {exc}")
    payload = st.session_state.get("last_search_payload")
    if payload:
        st.divider()
        st.markdown("### Latest search result")
        st.write(f"**Type:** {payload['kind']} · **Identifier:** {payload['identifier']}")
        if payload["kind"] == "dbSNP":
            st.success("RefSNP record retrieved and saved locally.")
            st.json(payload["summary"])
        elif payload["kind"] == "ClinVar":
            for record in payload["records"]:
                st.write(f"**{record.get('title', 'ClinVar record')}**")
                st.write(f"Variation ID: {record.get('uid', 'not supplied')}")
                st.write(f"Clinical significance: {record.get('clinical_significance', {}).get('description', 'Not supplied') if isinstance(record.get('clinical_significance'), dict) else 'Not supplied'}")
                st.json(record)
        elif payload["kind"] == "Gene":
            st.success("Gene record retrieved. Open Gene Explorer to view the full profile.")


def variant_analysis():
    st.subheader("Variant Analysis")
    current = st.session_state.current_variant
    with st.form("analysis_variant_form"):
        entered = st.text_input("rsID", value=current or "", placeholder="rs7412")
        run = st.form_submit_button("Analyse variant", type="primary")
    if run:
        try:
            st.session_state.current_variant = normalize_rsid(entered)
            current = st.session_state.current_variant
        except ValueError as exc:
            st.error(str(exc))
            return
    current = st.session_state.current_variant
    if not current:
        st.info("Search for an rsID first, or enter one above to begin analysis.")
        return
    st.markdown(f"### 🔬 {current}")
    section = st.radio("Analysis section", ["Identification", "Molecular consequences", "ClinVar evidence", "Population frequency"], horizontal=True)
    if section == "Identification":
        cached = st.session_state.db.get_variant(current, "NCBI dbSNP")
        if not cached:
            try:
                with st.spinner("Retrieving dbSNP record…"):
                    raw = st.session_state.clients["dbsnp"].get_ref_snp(current)
                    _save_dbsnp_record(current, raw)
                cached = st.session_state.db.get_variant(current, "NCBI dbSNP")
            except APIError as exc:
                st.error(str(exc))
        if cached:
            raw = cached.get("raw_data", {})
            summary = DbSNPClient.summarize(raw)
            a, b, c = st.columns(3)
            a.metric("RefSNP ID", raw.get("refsnp_id", "Not supplied"))
            b.metric("Created", raw.get("create_date", "Not supplied")[:10])
            c.metric("Last updated", raw.get("last_update_date", "Not supplied")[:10])
            st.write("**Assembly:**", summary.get("assembly") or "Not resolved from this record")
            st.write("**Chromosome:**", summary.get("chromosome") or "Not resolved from this record")
            st.write("**Position (1-based):**", summary.get("position") or "Not resolved from this record")
            st.write("**Alleles:**", f"{summary.get('ref_allele')} → {summary.get('alt_allele')}" if summary.get("ref_allele") else "Not resolved from this record")
            st.caption(f"Source: NCBI Variation Services · Retrieved: {cached['retrieved_at']}")
            with st.expander("Raw RefSNP JSON"):
                st.json(raw)
        else:
            st.warning("No cached dbSNP record is available.")
    elif section == "Molecular consequences":
        try:
            with st.spinner("Requesting Ensembl Variant Effect Predictor…"):
                records = st.session_state.clients["ensembl"].variant_effect(current)
            if not records:
                st.info("Ensembl VEP returned no consequence records for this identifier.")
            for record in records:
                st.write("**Most severe consequence:**", record.get("most_severe_consequence", "Not supplied"))
                st.write("**Location:**", record.get("location", "Not supplied"))
                st.write("**Allele string:**", record.get("allele_string", "Not supplied"))
                consequences = record.get("transcript_consequences", [])
                if consequences:
                    display = []
                    for item in consequences[:30]:
                        display.append({"Gene": item.get("gene_symbol"), "Transcript": item.get("transcript_id"),
                                        "Consequence": ", ".join(item.get("consequence_terms", [])),
                                        "Protein change": item.get("amino_acids"), "Protein position": item.get("protein_start")})
                    st.dataframe(display, use_container_width=True, hide_index=True)
                with st.expander("Raw Ensembl VEP response"):
                    st.json(record)
        except APIError as exc:
            st.error(str(exc))
    elif section == "ClinVar evidence":
        try:
            with st.spinner("Searching ClinVar by rsID…"):
                records = st.session_state.clients["clinvar"].search_by_term(current)
            if not records:
                st.info("No ClinVar records were returned for this rsID. This does not mean the variant is benign; it means this search returned no linked record.")
            for record in records:
                st.markdown(f"**{record.get('title', 'ClinVar submission')}**")
                clinical = record.get("clinical_significance") or {}
                if isinstance(clinical, dict):
                    st.write("**Clinical significance:**", clinical.get("description", "Not supplied"))
                    st.write("**Review status:**", clinical.get("review_status", "Not supplied"))
                st.write("**Variation ID (Entrez UID):**", record.get("uid", "Not supplied"))
                with st.expander("ClinVar summary JSON"):
                    st.json(record)
        except APIError as exc:
            st.error(str(exc))
    else:
        st.info("Population-frequency analysis is intentionally deferred in this stable build. gnomAD lookups require a normalized chromosome-position-reference-alternate representation and a dataset-specific GraphQL query. GENOVISTA will not guess frequencies from an rsID or display missing values as zero.")


def research_library():
    st.subheader("Research Library")
    db = st.session_state.db
    genes, variants = db.list_genes(), db.list_variants()
    st.markdown("#### Saved genes")
    if genes:
        st.dataframe([{"Gene": g["gene_symbol"], "Ensembl ID": g.get("ensembl_gene_id"),
                       "Chromosome": g.get("chromosome"), "Assembly": g.get("assembly"),
                       "Retrieved": g.get("retrieved_at")} for g in genes], use_container_width=True, hide_index=True)
    else:
        st.caption("No genes saved yet.")
    st.markdown("#### Saved variant records")
    if variants:
        st.dataframe([{"Identifier": v["variant_id"], "Source": v["source"],
                       "Gene": v.get("gene_symbol"), "Chromosome": v.get("chromosome"),
                       "Position": v.get("position"), "Retrieved": v.get("retrieved_at")} for v in variants],
                     use_container_width=True, hide_index=True)
        payload = json.dumps(variants, indent=2, ensure_ascii=False)
        st.download_button("Export saved records (JSON)", payload, "genovista_research_library.json", "application/json")
        output = io.StringIO()
        fields = ["variant_id", "source", "record_id", "gene_symbol", "chromosome", "position", "ref_allele", "alt_allele", "assembly", "retrieved_at"]
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(variants)
        st.download_button("Export variant index (CSV)", output.getvalue(), "genovista_variant_index.csv", "text/csv")
    else:
        st.caption("No variants saved yet.")


def about():
    st.subheader("About GENOVISTA")
    st.write(f"Version {__version__}")
    st.write("GENOVISTA retrieves authentic human gene and variant records from public resources. It does not generate synthetic sequences, fake patient records, or invented clinical assertions.")
    st.markdown("**Integrated sources**\n- Ensembl REST API — human gene lookup and Variant Effect Predictor.\n- NCBI Variation Services — dbSNP RefSNP records.\n- NCBI ClinVar via E-utilities — submitted clinical variation summaries.")
    st.markdown("**Deferred feature**\n- gnomAD population frequencies are not exposed in this stable build until the app can resolve a normalized allele representation and validate the current gnomAD GraphQL schema.")
    st.markdown("**Data interpretation**\n- A ClinVar classification is a submitted assertion with review status, not a personal diagnosis.\n- No result is different from a benign result.\n- Missing allele frequencies are not zero.\n- Genome assembly and source provenance are shown when supplied by the source.")
    st.caption("For research and educational use only. Not for clinical decision-making.")


def main():
    initialize_state()
    show_header()
    pages = ["Overview", "Gene Explorer", "Variant Search", "Variant Analysis", "Research Library", "About & Data Sources"]
    page = st.sidebar.radio("Navigation", pages, index=0)
    st.sidebar.divider()
    st.sidebar.caption("Public data · Local cache · No synthetic records")
    if page == "Overview": overview()
    elif page == "Gene Explorer": gene_explorer()
    elif page == "Variant Search": variant_search()
    elif page == "Variant Analysis": variant_analysis()
    elif page == "Research Library": research_library()
    else: about()


if __name__ == "__main__":
    main()
