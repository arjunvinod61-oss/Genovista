import json
from genovista.database import Database
from genovista.validators import normalize_rsid, normalize_gene_symbol, normalize_clinvar_accession
from genovista.services import DbSNPClient


def test_identifier_normalization():
    assert normalize_rsid(" RS7412 ") == "rs7412"
    assert normalize_gene_symbol("brca1") == "BRCA1"
    assert normalize_clinvar_accession("vcv000014206") == "VCV000014206"


def test_invalid_identifiers():
    for fn, value in [(normalize_rsid, "BRCA1"), (normalize_gene_symbol, ""),
                      (normalize_clinvar_accession, "rs7412")]:
        try:
            fn(value)
        except ValueError:
            pass
        else:
            raise AssertionError(f"{fn.__name__} should reject {value!r}")


def test_database_gene_roundtrip(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    gene = {"gene_symbol": "BRCA1", "ensembl_gene_id": "ENSG00000012048",
            "chromosome": "17", "start": 43044292, "end": 43170245,
            "strand": -1, "assembly": "GRCh38", "description": "BRCA1 DNA repair associated",
            "source": "Ensembl REST", "raw_data": {"id": "ENSG00000012048"}}
    db.save_gene(gene)
    saved = db.get_gene("brca1")
    assert saved["ensembl_gene_id"] == "ENSG00000012048"
    assert saved["start_position"] == 43044292
    assert saved["raw_data"]["id"] == "ENSG00000012048"
    assert len(db.list_genes()) == 1
    db.close()


def test_database_variant_roundtrip_and_list(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    raw = {"refsnp_id": "7412", "create_date": "2000-09-19"}
    db.save_variant("rs7412", "NCBI dbSNP", raw, record_id="7412", chromosome="19", position=44908822)
    saved = db.get_variant("rs7412", "NCBI dbSNP")
    assert saved["raw_data"]["refsnp_id"] == "7412"
    assert saved["position"] == 44908822
    assert len(db.list_variants()) == 1
    assert db.delete_variant("rs7412", "NCBI dbSNP") is True
    assert db.get_variant("rs7412", "NCBI dbSNP") is None
    db.close()


def test_dbsnp_summary_does_not_mistake_accession_for_chromosome():
    sample = {"primary_snapshot_data": {"placements_with_allele": [{
        "placement_annot": {"seq_id_traits_by_assembly": [{
            "assembly_name": "GRCh38.p14", "seq_id": "NC_000019.10", "chromosome": "19"}]},
        "alleles": [{"allele": {"spdi": {"seq_id": "NC_000019.10", "position": 10,
                                               "deleted_sequence": "A", "inserted_sequence": "G"}}}]
    }]}}
    result = DbSNPClient.summarize(sample)
    assert result["chromosome"] == "19"
    assert result["position"] == 11
    assert result["ref_allele"] == "A"
    assert result["alt_allele"] == "G"


def test_ensembl_vep_accepts_list_response(monkeypatch):
    from genovista.services import EnsemblClient
    client = EnsemblClient()
    monkeypatch.setattr(client, "get_json", lambda *a, **k: [{"id": "rs7412", "most_severe_consequence": "missense_variant"}])
    records = client.variant_effect("rs7412")
    assert isinstance(records, list)
    assert records[0]["most_severe_consequence"] == "missense_variant"


def test_dbsnp_summary_prefers_grch38_even_if_grch37_is_first():
    sample = {"primary_snapshot_data": {"placements_with_allele": [
        {"placement_annot": {"seq_id_traits_by_assembly": [
            {"assembly_name": "GRCh37.p13", "seq_id": "NC_000019.9", "chromosome": "19"}]},
         "alleles": [{"allele": {"spdi": {"seq_id": "NC_000019.9", "position": 1,
                                                "deleted_sequence": "C", "inserted_sequence": "T"}}}]},
        {"placement_annot": {"seq_id_traits_by_assembly": [
            {"assembly_name": "GRCh38.p14", "seq_id": "NC_000019.10", "chromosome": "19"}]},
         "alleles": [{"allele": {"spdi": {"seq_id": "NC_000019.10", "position": 9,
                                                "deleted_sequence": "C", "inserted_sequence": "T"}}}]}
    ]}}
    result = DbSNPClient.summarize(sample)
    assert result["assembly"].startswith("GRCh38")
    assert result["position"] == 10
