import csv
import argparse
from pathlib import Path


def get_xor_values(xor_map_filepath: Path) -> set[int]:
    out: set[int] = set()
    with xor_map_filepath.open(mode="r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            out.add(int(row[0], 16))
    return out


def build_round_1_map(xor_values: set[int]):
    checksum_map: dict[int, int] = {}
    for xor_value in sorted(xor_values):
        remainder = (0x10000 - (xor_value * 12)) & 0xFFFF
        for i in range(remainder, 0xC0000, 0x10000):
            if (i % 12) == 0 and (i // 12) in xor_values and ((i // 12) & 0x4000 == 0):
                checksum_map[xor_value] = i // 12
                break
    return checksum_map


def calc_messages(target_species: int,
                  xor_values: set[int],
                  round_1_map: dict[int, int]) -> list[list[tuple[int, int]]]:
    if target_species not in xor_values:
        raise ValueError("Species cannot be generated with provided xor map", target_species)
    MASK_16 = (1 << 16) - 1
    messages: list[list[tuple[int, int]]] = []
    if target_species in round_1_map:
        messages.append([(target_species, round_1_map[target_species])])
    # Allow for second round in case the first round result produces an egg
    # and species is unhatchable (e.g. causes a crash upon hatching)
    # key_low determines species in an empty slot
    # key_high determines whether the resulting Pokémon is an egg, and what
    # item it is holding.
    for key_low, key_high in round_1_map.items():
        base_message = [(key_low, key_high)]
        target_checksum = (1 << 16) - key_high
        encrypted_item = key_high
        for new_key_high in xor_values:
            if new_key_high & 0x4000 == 0x4000:
                continue
            message = base_message.copy()
            checksum = (((target_species * 12)
                            + (new_key_high * 11)
                            + (new_key_high ^ encrypted_item))
                        & MASK_16)
            if checksum == target_checksum:
                message.append((target_species, new_key_high))
                messages.append(message)
    return messages


def write_results(results: list[list[tuple[int, int]]], out: Path):
    with out.open(mode="w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["Mail 1 Key Low", "Mail 1 Key High", "Mail 2 Key Low", "Mail 2 Key High"])
        for result in results:
            row: list[str] = []
            for message in result:
                row.extend((f"{x:04X}" for x in message))
            writer.writerow(row)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("xor_map",
                        type=Path,
                        help="Path to the xor map file")
    parser.add_argument("target_species",
                        type=lambda x: int(x, 0),
                        help="The target species from the mail message sequences")
    parser.add_argument("-o", "--out",
                        type=Path,
                        default=(Path(__file__).parent / "results.csv"),
                        help="Output file location with the results")
    a = parser.parse_args()
    xor_values = get_xor_values(a.xor_map)
    round_1_map = build_round_1_map(xor_values)
    results = calc_messages(a.target_species, xor_values, round_1_map)
    write_results(results, a.out)
    


if __name__ == "__main__":
    main()
