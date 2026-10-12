import re


def parse_ovs_port_stats(raw_output):
    records = []
    current = None

    for line in raw_output.splitlines():
        line = line.strip()

        if line.startswith("port "):
            match = re.match(r"port\s+(.*?):\s+rx", line)
            if match:
                name = match.group(1).strip().strip(chr(34))
                current = {"port": name}
                records.append(current)

                rx = re.search(r"rx pkts=(\d+), bytes=(\d+), drop=(\d+), errs=(\d+)", line)
                if rx:
                    current.update({"rx_packets": int(rx.group(1)), "rx_bytes": int(rx.group(2)), "rx_dropped": int(rx.group(3)), "rx_errors": int(rx.group(4))})

        elif line.startswith("tx pkts=") and current is not None:
            tx = re.search(r"tx pkts=(\d+), bytes=(\d+), drop=(\d+), errs=(\d+)", line)
            if tx:
                current.update({"tx_packets": int(tx.group(1)), "tx_bytes": int(tx.group(2)), "tx_dropped": int(tx.group(3)), "tx_errors": int(tx.group(4))})

    return records
