import csv
import argparse
import unicodedata
from itertools import combinations_with_replacement
from pathlib import Path
from typing import NamedTuple


CURRENT_FOLDER = Path(__file__).parent


class EasyChatEntry(NamedTuple):
    group: str
    word: str


def normalise_input(input_str: str):
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    return "".join([
        c for c in nfkd_form
        if not unicodedata.combining(c)
        ]).upper()


def read_target_indexes(indexes: list[int]) -> set[int]:
    return set(indexes)


def read_exclude_groups(eg_arg: list[str] | None):
    WORD_GROUPS = [
        "???",
        "POKéMON2",
        "TRAINER",
        "STATUS",
        "BATTLE",
        "GREETINGS",
        "PEOPLE",
        "VOICES",
        "SPEECH",
        "ENDINGS",
        "FEELINGS",
        "CONDITIONS",
        "ACTIONS",
        "LIFESTYLE",
        "HOBBIES",
        "TIME",
        "MISC.",
        "ADJECTIVES",
        "EVENTS",
        "MOVE 1",
        "MOVE 2",
        "POKéMON",
    ]
    group_map = {
        normalise_input(word_group): word_group
        for word_group in WORD_GROUPS
        }
    exclude_groups: set[str] = set()
    if eg_arg is not None:
        for group in eg_arg:
            if (g := normalise_input(group)) not in group_map:
                raise ValueError("Not a word group", group)
            exclude_groups.add(group_map[g])
    return exclude_groups


def read_exclude_ranges(
        easy_chat_data: dict[int, EasyChatEntry],
        exclude_ranges: list[int] | None,
        exclude_groups: set[str]
        ):
    exclude_indexes: set[int] = set()
    if exclude_ranges is not None:
        if len(exclude_ranges) % 2 != 0:
            raise ValueError("Provided input does not evenly split into ranges")
        for lower, upper in zip(exclude_ranges[::2], exclude_ranges[1::2]):
            exclude_indexes.update(range(lower, upper+1))
    exclude_indexes.update(
        (word_index
         for word_index, word_entry in easy_chat_data.items()
         if word_entry.group in exclude_groups)
        )
    return exclude_indexes


def get_easy_chat_words(easy_chat_csv: Path):
    with easy_chat_csv.open(mode="r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        next(reader)
        data = {int(x[0], 16): EasyChatEntry(group=x[1], word=x[2]) for x in reader}
    return data


def calc_xor_combinations(
        easy_chat_data: dict[int, EasyChatEntry],
        exclude_indexes: set[int],
        filter_values: set[int]
        ):
    # The purpose of this scoretable is to facilitate
    # favouring some combination of easy chat words over
    # others based on their unlockability, as well as usability.
    #
    # ??? (word index 0 for empty box slots) is also given a score
    # despite not being a word group due to being an invalid 'word'
    # thus not enterable with the easy chat system. It is only provided
    # as all halfwords are populated with this index when using mail corruption
    # on an empty box slot.
    WORD_GROUP_SCORETABLE = {
        "???": 1,
        "POKéMON2": 11,
        "TRAINER": 0,
        "STATUS": 0,
        "BATTLE": 0,
        "GREETINGS": 0,
        "PEOPLE": 0,
        "VOICES": 0,
        "SPEECH": 0,
        "ENDINGS": 0,
        "FEELINGS": 0,
        "CONDITIONS": 0,
        "ACTIONS": 0,
        "LIFESTYLE": 0,
        "HOBBIES": 0,
        "TIME": 0,
        "MISC.": 0,
        "ADJECTIVES": 0,
        "EVENTS": 5,
        "MOVE 1": 5,
        "MOVE 2": 5,
        "POKéMON": 2,
        "-----": 0
    }
    xor_map: dict[int, tuple[int, int]] = {}
    for (w1_index, w1), (w2_index, w2) in (
        combinations_with_replacement(easy_chat_data.items(), r=2)):
        xor_value = w1_index ^ w2_index
        if (w1_index in exclude_indexes
            or w2_index in exclude_indexes):
            continue
        if xor_value not in filter_values:
            continue
        if xor_value in xor_map:
            cur_entry = xor_map[xor_value]
            cur_score = sum((WORD_GROUP_SCORETABLE[w.group]
                             for w in (easy_chat_data[i] for i in cur_entry)))
            new_score = sum((WORD_GROUP_SCORETABLE[w.group] for w in (w1, w2)))
            if new_score >= cur_score:
                continue
        xor_map[w1_index ^ w2_index] = (w1_index, w2_index)
    return xor_map


def write_csv(
        output_path: Path,
        xor_map: dict[int, tuple[int, int]],
        easy_chat_data: dict[int, EasyChatEntry]
        ):
    with output_path.open(mode="w",
                          encoding="utf-8",
                          newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow([
            "XOR value",
            "Word 1 index",
            "Word 1 group",
            "Word 1",
            "Word 2 index",
            "Word 2 group",
            "Word 2"
            ])
        for n, (w1_i, w2_i) in sorted(xor_map.items()):
            writer.writerow([
                f"{n:04X}",
                f"{w1_i:04X}",
                f"{easy_chat_data[w1_i].group}",
                f"{easy_chat_data[w1_i].word}",
                f"{w2_i:04X}",
                f"{easy_chat_data[w2_i].group}",
                f"{easy_chat_data[w2_i].word}",
                ])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("easy_chat_data",
                        type=Path,
                        help="Path to csv with easy chat system words")
    parser.add_argument("-o", "--out",
                        type=Path,
                        default=(CURRENT_FOLDER / "out.csv"),
                        help="Output file path")
    parser.add_argument("-f", "--filter-values",
                        type=lambda x: int(x, 0),
                        nargs='+',
                        default=list(range(0, 1 << 16)),
                        help="Filter xor map to these xor values only (leave blank to for unfiltered output)")
    parser.add_argument("--exclude-group",
                        nargs='+',
                        help="Word groups to exclude from the xor map")
    parser.add_argument("--exclude-range",
                        type=lambda x: int(x, 0),
                        nargs='+',
                        help="Word indexes to exclude from the xor map")
    a = parser.parse_args()
    easy_chat_data = get_easy_chat_words(a.easy_chat_data)
    filter_values = read_target_indexes(a.filter_values)
    exclude_groups = read_exclude_groups(a.exclude_group)
    exclude_indexes = read_exclude_ranges(easy_chat_data=easy_chat_data,
                                          exclude_ranges=a.exclude_range,
                                          exclude_groups=exclude_groups)
    xor_map = calc_xor_combinations(
        easy_chat_data=easy_chat_data,
        exclude_indexes=exclude_indexes,
        filter_values=filter_values
        )
    write_csv(a.out, xor_map, easy_chat_data)


if __name__ == "__main__":
    main()
