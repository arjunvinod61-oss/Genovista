"""Small, provenance-aware SQLite cache. No synthetic records are created."""
from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

DEFAULT_DB = Path(__file__).resolve().parent / "genovista.sqlite3"


class Database:
    def __init__(self, path: str | Path = DEFAULT_DB):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._create_schema()

    def _create_schema(self):
        self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS genes (
            gene_symbol TEXT PRIMARY KEY,
            ensembl_gene_id TEXT,
            chromosome TEXT,
            start_position INTEGER,
            end_position INTEGER,
            strand INTEGER,
            assembly TEXT,
            description TEXT,
            source TEXT NOT NULL,
            retrieved_at TEXT NOT NULL,
            raw_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS variants (
            variant_id TEXT NOT NULL,
            source TEXT NOT NULL,
            record_id TEXT,
            gene_symbol TEXT,
            chromosome TEXT,
            position INTEGER,
            ref_allele TEXT,
            alt_allele TEXT,
            assembly TEXT,
            retrieved_at TEXT NOT NULL,
            raw_json TEXT NOT NULL,
            PRIMARY KEY (variant_id, source)
        );
        CREATE INDEX IF NOT EXISTS idx_variants_gene ON variants(gene_symbol);
        CREATE INDEX IF NOT EXISTS idx_variants_saved ON variants(retrieved_at);
        """)
        self.conn.commit()

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    @staticmethod
    def _decode(row):
        if row is None:
            return None
        data = dict(row)
        if "raw_json" in data:
            try:
                data["raw_data"] = json.loads(data.pop("raw_json"))
            except (TypeError, json.JSONDecodeError):
                data["raw_data"] = None
        return data

    def save_gene(self, gene: dict[str, Any]) -> None:
        symbol = gene["gene_symbol"].upper()
        raw = gene.get("raw_data", gene)
        self.conn.execute("""INSERT INTO genes
            (gene_symbol, ensembl_gene_id, chromosome, start_position, end_position,
             strand, assembly, description, source, retrieved_at, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(gene_symbol) DO UPDATE SET
             ensembl_gene_id=excluded.ensembl_gene_id,
             chromosome=excluded.chromosome, start_position=excluded.start_position,
             end_position=excluded.end_position, strand=excluded.strand,
             assembly=excluded.assembly, description=excluded.description,
             source=excluded.source, retrieved_at=excluded.retrieved_at,
             raw_json=excluded.raw_json""",
            (symbol, gene.get("ensembl_gene_id"), gene.get("chromosome"),
             gene.get("start"), gene.get("end"), gene.get("strand"),
             gene.get("assembly"), gene.get("description"),
             gene.get("source", "Ensembl REST"), self._now(),
             json.dumps(raw, ensure_ascii=False)))
        self.conn.commit()

    def get_gene(self, symbol: str):
        row = self.conn.execute("SELECT * FROM genes WHERE gene_symbol=?", (symbol.upper(),)).fetchone()
        return self._decode(row)

    def list_genes(self):
        rows = self.conn.execute("SELECT * FROM genes ORDER BY retrieved_at DESC").fetchall()
        return [self._decode(r) for r in rows]

    def save_variant(self, variant_id: str, source: str, raw_data: dict,
                     record_id: str | None = None, gene_symbol: str | None = None,
                     chromosome: str | None = None, position: int | None = None,
                     ref_allele: str | None = None, alt_allele: str | None = None,
                     assembly: str | None = None):
        self.conn.execute("""INSERT INTO variants
            (variant_id, source, record_id, gene_symbol, chromosome, position,
             ref_allele, alt_allele, assembly, retrieved_at, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(variant_id, source) DO UPDATE SET
             record_id=excluded.record_id, gene_symbol=excluded.gene_symbol,
             chromosome=excluded.chromosome, position=excluded.position,
             ref_allele=excluded.ref_allele, alt_allele=excluded.alt_allele,
             assembly=excluded.assembly, retrieved_at=excluded.retrieved_at,
             raw_json=excluded.raw_json""",
            (variant_id, source, record_id, gene_symbol, chromosome, position,
             ref_allele, alt_allele, assembly, self._now(),
             json.dumps(raw_data, ensure_ascii=False)))
        self.conn.commit()

    def get_variant(self, variant_id: str, source: str | None = None):
        if source:
            row = self.conn.execute("SELECT * FROM variants WHERE variant_id=? AND source=?",
                                    (variant_id, source)).fetchone()
            return self._decode(row)
        rows = self.conn.execute("SELECT * FROM variants WHERE variant_id=? ORDER BY retrieved_at DESC",
                                 (variant_id,)).fetchall()
        return [self._decode(r) for r in rows]

    def list_variants(self):
        rows = self.conn.execute("SELECT * FROM variants ORDER BY retrieved_at DESC").fetchall()
        return [self._decode(r) for r in rows]

    def delete_variant(self, variant_id: str, source: str):
        cur = self.conn.execute("DELETE FROM variants WHERE variant_id=? AND source=?", (variant_id, source))
        self.conn.commit()
        return cur.rowcount > 0

    def close(self):
        self.conn.close()
