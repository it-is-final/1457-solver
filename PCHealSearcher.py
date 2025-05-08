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


def read_moves_csv(moves_csv_filepath: Path) -> dict[int, int]:
    with moves_csv_filepath.open(mode="r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)
        out = {int(x[0]): int(x[1]) for x in reader}
    return out


def calc_move_pp(base_pp: int, pp_ups: int):
    return (base_pp + ((base_pp // 5) * pp_ups)) % 256


def get_round_1(
        key_lows: set[int],
        key_highs: set[int]):
    MAX_CHECKSUM = 0xFFFF * 24
    round_1: dict[int, list[int]] = {}
    for key_low in sorted(key_lows):
        for checksum in range(0, MAX_CHECKSUM, 3 << 16):
            key_high = (checksum - (key_low * 12)) // 12
            if key_high not in key_highs:
                continue
            if key_low not in round_1:
                round_1[key_low] = []
            round_1[key_low].append(key_high)
    return round_1


def get_round_2(
        xor_values: set[int],
        key_lows: list[int],
        key_highs: set[int],
        move_pps: dict[int, int],
    ):
    round_2_to_round_1: dict[int, tuple[int, int]] = {}
    round_2: dict[int, int] = {}
    round_1 = (
        (key_low, key_high)
        for key_low, _key_highs in get_round_1(xor_values, xor_values).items()
        for key_high in _key_highs
        )
    for low1, high1 in round_1:
        # Avoid species 0 (??????????) as it is considered "no Pokemon"
        if low1 == 0:
            continue
        pp_ups = {
            0: (low1 >> 0) & 0b11,
            1: (low1 >> 2) & 0b11,
            2: (low1 >> 4) & 0b11,
            3: (low1 >> 6) & 0b11,
        }
        pps = {
            0: calc_move_pp(move_pps[low1], pp_ups[0]),
            1: calc_move_pp(move_pps[high1], pp_ups[1]),
            2: calc_move_pp(move_pps[low1], pp_ups[2]),
            3: calc_move_pp(move_pps[high1], pp_ups[3]),
        }
        pps_low = ((pps[1] << 8) | (pps[0] << 0))
        pps_high = ((pps[3] << 8) | (pps[2] << 0))
        checksum = ((low1 * 11) + (high1 * 11)
                    + pps_low + pps_high)
        pps_low ^= low1
        pps_high ^= high1
        for low2 in key_lows:
            if low2 in round_2:
                continue
            a = checksum - (11 * low2) - (pps_low ^ low2)
            solutions = [0]
            one_hot = 1
            mask = 1
            # Credits to Shao on Glitch City Research Institute Discord server for
            # a more efficient method of finding the other XOR word.
            # Solutions are built bit-by-bit since operations involved mask high bits
            while one_hot < (1 << 16):
                new_solutions: list[int] = []
                for solution in solutions:
                    # Check if bit set to 0 works
                    if ((11 * solution + (pps_high ^ solution)) & mask) == (a & mask):
                        new_solutions.append(solution)
                    solution |= one_hot
                    # Check if bit set to 1 works
                    if ((11 * solution + (pps_high ^ solution)) & mask) == (a & mask):
                        new_solutions.append(solution)
                solutions.clear()
                solutions.extend(new_solutions)
                one_hot <<= 1
                mask = (mask << 1) | 1
            for solution in solutions:
                if solution not in key_highs:
                    continue
                if low2 not in round_2:
                    round_2[low2] = solution
                    round_2_to_round_1[low2] = (low1, high1)
                break
    return round_2, round_2_to_round_1


def write_map(round_map: dict[int, list[int]], out: Path):
    with out.open(mode="w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["Mail 1 Key Low", "Mail 1 Key High"])
        for key_low, key_highs in round_map.items():
            for key_high in key_highs:
                writer.writerow([hex(key_low), hex(key_high)])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("xor_map",
                        type=Path,
                        help="Path to the xor map file")
    parser.add_argument("moves_pp_csv",
                        type=Path,
                        help="Path to the moves pp csv file")
    a = parser.parse_args()
    xor_values = get_xor_values(a.xor_map)
    move_pps = read_moves_csv(a.moves_pp_csv)
    round_1 = get_round_1(
                    xor_values,
                    {x for x in xor_values if x & 0x4000 == 0},
                    )
    round_2, _ = get_round_2(
                    xor_values=xor_values,
                    key_lows=[x for x in xor_values if x not in round_1],
                    key_highs={x for x in xor_values if x & 0x4000 == 0},
                    move_pps=move_pps,
                    )
    round_3_needed = xor_values - (round_1.keys() | round_2.keys())
    print(f"""\
{len(round_1)} round 1 species
{len(round_2)} round 2 species
{len(round_1) + len(round_2)} species able to be generated in two rounds
Species not in round 1 or 2: {{{", ".join(hex(x) for x in round_3_needed)}}}
""")


if __name__ == "__main__":
    main()
