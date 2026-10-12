import time
import json
import sqlite3
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = Path(os.environ.get("CN_TELEMETRY_DB", PROJECT_ROOT / "telemetry" / "data" / "telemetry.db"))

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from security.trust_layer import audit_event, validate_telemetry_metrics


def get_database_connection():
    return sqlite3.connect(DB_PATH)


def store_telemetry(source, node, port, metrics):
    if not isinstance(source, str) or not source.strip():
        raise ValueError("source must be a non-empty string")
    if not isinstance(node, str) or not node.strip():
        raise ValueError("node must be a non-empty string")
    valid, reason = validate_telemetry_metrics(metrics)
    if not valid:
        audit_event("telemetry_ingress", "rejected", source=source, node=node, reason=reason)
        raise ValueError(f"Rejected telemetry: {reason}")
    conn = get_database_connection()

    conn.execute(
        """
        INSERT INTO telemetry
        (timestamp, source, node, port, metrics_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            time.time(),
            source,
            node,
            port,
            json.dumps(metrics),
        ),
    )

    conn.commit()
    conn.close()


def get_latest_telemetry(limit=10):
    conn = get_database_connection()

    rows = conn.execute(
        """
        SELECT id, timestamp, source, node, port, metrics_json
        FROM telemetry
        ORDER BY timestamp DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    conn.close()
    return rows


def pipeline_health_check():
    conn = get_database_connection()

    conn.execute("SELECT 1").fetchone()
    count = conn.execute("SELECT COUNT(*) FROM telemetry").fetchone()[0]

    conn.close()

    return {
        "database": "connected",
        "telemetry_rows": count,
    }


def format_telemetry_row(row):
    return {
        "id": row[0],
        "timestamp": row[1],
        "source": row[2],
        "node": row[3],
        "port": row[4],
        "metrics": json.loads(row[5]),
    }


def get_formatted_telemetry(limit=10):
    rows = get_latest_telemetry(limit)
    return [format_telemetry_row(row) for row in rows]


def get_time_ordered_telemetry(limit=10):
    records = get_formatted_telemetry(limit)
    return list(reversed(records))


def pipeline_status():
    records = get_formatted_telemetry(1)

    return {
        "status": "active" if records else "empty",
        "latest_record_id": records[0]["id"] if records else None,
        "latest_timestamp": records[0]["timestamp"] if records else None,
        "latest_source": records[0]["source"] if records else None,
        "latest_node": records[0]["node"] if records else None,
        "latest_port": records[0]["port"] if records else None,
    }


SAMPLE_INTERVAL = 5


def collect_one_sample():
    records = get_formatted_telemetry(1)

    if not records:
        return None

    return records[0]


def run_collection_loop(sample_count=3):
    samples = []

    for _ in range(sample_count):
        sample = collect_one_sample()

        if sample is not None:
            samples.append(sample)
            print(
                f"Collected telemetry: "
                f"id={sample['id']} "
                f"node={sample['node']} "
                f"port={sample['port']}"
            )

        time.sleep(SAMPLE_INTERVAL)

    return samples


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ovs_telemetry import get_ovs_port_stats
from ovs_parser import parse_ovs_port_stats


def collect_ovs_sample(switch="s1"):
    result = get_ovs_port_stats(switch)

    if result["return_code"] != 0:
        return {
            "success": False,
            "error": result["stderr"].strip(),
            "records": [],
        }

    records = parse_ovs_port_stats(result["stdout"])

    stored_records = 0
    for record in records:
        port = str(record.get("port", ""))
        if not port:
            continue
        store_telemetry(
            source="ovs",
            node=switch,
            port=port,
            metrics=record,
        )
        stored_records += 1

    return {
        "success": True,
        "error": None,
        "records": records,
        "stored_records": stored_records,
    }


def run_ovs_collection_loop(switch="s1", sample_count=3):
    """Collect and persist fresh OVS port statistics at fixed intervals."""
    if not isinstance(sample_count, int) or isinstance(sample_count, bool) or sample_count < 1:
        raise ValueError("sample_count must be a positive integer")

    results = []

    for index in range(sample_count):
        result = collect_ovs_sample(switch)
        results.append(result)

        if result["success"]:
            print(
                f"OVS sample {index + 1}/{sample_count}: "
                f"switch={switch}, "
                f"ports={len(result['records'])}, "
                f"stored={result.get('stored_records', 0)}"
            )
        else:
            print(
                f"OVS sample {index + 1}/{sample_count} failed: "
                f"{result.get('error')}"
            )

        if index + 1 < sample_count:
            time.sleep(SAMPLE_INTERVAL)

    return results
