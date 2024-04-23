import csv
import os
import re
import json
from typing import Callable

from PIL import Image

import config
from util import awb_index, resource_path, song_id_from_int
from ui.data_setup import TaskProgress, TaskState
from ui.tabs.listing_tab import ListingTab
from .metadata import Difficulty, DifficultyName, SongMetadata

## NOTE: ID KEYS ARE HYPHENATED
## S03-014, not S03_014
metadata: dict[str, SongMetadata] = dict()
"""ID to SongMetadata"""

audio_index: dict[str, tuple[str, int]] = dict()
"""ID to AWB file and audio index"""

audio_file: dict[str, str] = dict()
"""ID to audio filename"""

jacket_preview: dict[str, Image.Image] = dict()
"""ID to resized PIL Image of jacket"""

jacket_file: dict[str, str] = dict()
"""ID to jacket filename"""

## MISSING CONTENT
missing_audio: list[str] = list()
"""List of songs missing audio"""

missing_jackets: list[str] = list()
"""List of songs missing jacket"""


# def init():
#     await _init_songs()
#     await _init_audio_index()
#     await _init_audio_paths()
#     await _init_jacket_paths()

#     print(f"{len(metadata)} songs' metadata found")
#     print(f"{len(jacket_file)} jackets found")
#     print(f"{len(audio_file)} audio files found")
#     print()

#     _populate_missing()
#     # print(audio_file)


def init_songs(progress: TaskProgress):
    metadata_path = os.path.join(config.working_path, "metadata.json")
    videos_dir = os.path.join(config.working_path, "movies")
    jackets_dir = os.path.join(config.working_path, "jackets")
    print(f"Initializing charts metadata from {metadata_path}...")

    metadata.clear()
    md_json: list
    try:
        with open(metadata_path, "r", encoding="utf_8") as read_file:
            md_json = json.load(read_file)["Exports"][0]["Table"]["Data"]

        for elem in md_json:  # songs
            id: str = None
            genre: int = None
            name: str = None
            artist: str = None
            rubi: str = None
            copyright: str = None
            tempo: str = None
            version: int = None
            audio_preview: str = None
            audio_preview_len: str = None
            background_video: list[str] = [None, None, None, None]
            levels: list[str] = [None, None, None, None]
            level_audio: list[str] = [None, None, None, None]  # from .mer
            level_designer: list[str] = [None, None, None, None]
            level_clear_requirements: list[str] = [None, None, None, None]
            jacket_path: str = None

            # MusicParameterTable JSON parsing
            for key in elem["Value"]:  # properties of song
                if key["Name"] == "AssetDirectory":
                    id = key["Value"]
                # SongInfo
                elif key["Name"] == "ScoreGenre":
                    genre = int(key["Value"])
                elif key["Name"] == "MusicMessage":
                    name = key["Value"]
                elif key["Name"] == "ArtistMessage":
                    artist = key["Value"]
                elif key["Name"] == "Rubi":
                    rubi = key["Value"]
                elif key["Name"] == "Bpm":
                    tempo = key["Value"]
                elif key["Name"] == "CopyrightMessage" and key["Value"] not in [
                    "",
                    "-",
                    None,
                ]:
                    copyright = key["Value"]
                elif key["Name"] == "VersionNo":
                    version = key["Value"]
                elif key["Name"] == "JacketAssetName":
                    jacket_path = key["Value"]
                # ChartInfo Levels; "+0" = no chart
                elif key["Name"] == "DifficultyNormalLv":
                    levels[0] = round(float(key["Value"]), 2)
                elif key["Name"] == "DifficultyHardLv":
                    levels[1] = round(float(key["Value"]), 2)
                elif key["Name"] == "DifficultyExtremeLv":
                    levels[2] = round(float(key["Value"]), 2)
                elif key["Name"] == "DifficultyInfernoLv":
                    levels[3] = round(float(key["Value"]), 2)
                # Audio Previews
                elif key["Name"] == "PreviewBeginTime":
                    audio_preview = round(float(key["Value"]), 2)
                elif key["Name"] == "PreviewSeconds":
                    audio_preview_len = round(float(key["Value"]), 2)
                # Clear Requirements
                elif key["Name"] == "ClearNormaRateNormal":
                    level_clear_requirements[0] = round(float(key["Value"]), 2)
                elif key["Name"] == "ClearNormaRateHard":
                    level_clear_requirements[1] = round(float(key["Value"]), 2)
                elif key["Name"] == "ClearNormaRateExtreme":
                    level_clear_requirements[2] = round(float(key["Value"]), 2)
                elif key["Name"] == "ClearNormaRateInferno":
                    level_clear_requirements[3] = round(float(key["Value"]), 2)
                # ChartInfo Designers
                elif key["Name"] == "NotesDesignerNormal":
                    level_designer[0] = key["Value"]
                elif key["Name"] == "NotesDesignerHard":
                    level_designer[1] = key["Value"]
                elif key["Name"] == "NotesDesignerExpert":
                    level_designer[2] = key["Value"]
                elif key["Name"] == "NotesDesignerInferno":
                    level_designer[3] = key["Value"]
                # Video Backgrounds
                elif key["Name"] == "MovieAssetName" and key["Value"] not in [
                    "",
                    "-",
                    None,
                ]:
                    background_video[0] = key["Value"]
                elif key["Name"] == "MovieAssetNameHard" and key["Value"] not in [
                    "",
                    "-",
                    None,
                ]:
                    background_video[1] = key["Value"]
                elif key["Name"] == "MovieAssetNameExpert" and key["Value"] not in [
                    "",
                    "-",
                    None,
                ]:
                    background_video[2] = key["Value"]
                elif key["Name"] == "MovieAssetNameInferno" and key["Value"] not in [
                    "",
                    "-",
                    None,
                ]:
                    background_video[3] = key["Value"]

            if "S99" in id:
                # print('Skipping system song...')
                continue

            # check for existence of video file
            for i, f in enumerate(background_video):
                if f is not None:
                    file = f"{f}.mp4"
                    path = os.path.join(os.path.join(videos_dir, file))
                    if not os.path.exists(path):
                        progress.log(
                            f"WARNING: Could not find video file for {id} ({DifficultyName(i)})!"
                        )
                        progress.log(f"    {path}")
                        background_video[i] = None
                    else:
                        background_video[i] = path

            # mer difficulty-audio IDs
            mer_dir = os.path.join(config.working_path, "MusicData", id)
            for _, _, files in os.walk(f"{mer_dir}"):
                for f in files:
                    diff_idx = int(re.search(r"\d\d.mer", f).group()[:2])

                    lines: list[str]
                    with open(os.path.join(mer_dir, f), "r") as chf:
                        lines = chf.readlines()
                    a_id = None
                    offset = None
                    for l in lines:
                        if "MUSIC_FILE_PATH" in l:
                            a_id = re.search(r"S\d\d_\d\d\d", l.split()[1]).group()
                        elif "OFFSET" in l:
                            offset = l.split()[1]
                        if a_id and offset:
                            break

                    a_id = a_id.replace("_", "-")
                    level_audio[diff_idx] = (a_id, offset)

            # difficulty iteration -- level_audio has None for diffs w/o chart
            difficulties: list[Difficulty] = [None, None, None, None]
            for i, audio in enumerate(level_audio):
                if audio is None:
                    continue
                diff = Difficulty(
                    audio_id=audio[0],
                    audio_offset=audio[1],
                    audio_preview_time=audio_preview,
                    audio_preview_duration=audio_preview_len,
                    video=background_video[i],
                    designer=level_designer[i],
                    clearRequirement=level_clear_requirements[i],
                    diffLevel=levels[i],
                )
                # use base video bg if video bg for this diff doesn't exist
                if (
                    i != 0
                    and background_video[i] is None
                    and background_video[0] is not None
                ):
                    diff.video = background_video[0]
                difficulties[i] = diff

            # jacket path to png
            mer_root = os.path.join(jackets_dir, *jacket_path.split("/"))
            if os.path.isdir(mer_root):
                for f in os.listdir(mer_root):
                    if f.endswith(".png"):
                        jacket_path = os.path.join(mer_root, f)
                        break
            else:
                jacket_path = f"{mer_root}.png"

            if jacket_path is None or not os.path.exists(jacket_path):
                jacket_path = None
                progress.log(f"WARNING: Could not find jacket for {id}!")

            metadata[id] = SongMetadata(
                id=id,
                name=name,
                artist=artist,
                rubi=rubi,
                genre_id=genre,
                copyright=copyright,
                tempo=tempo,
                version=version,
                difficulties=difficulties,
                jacket=jacket_path,
            )
    except Exception as e:
        progress.log(f"FATAL: Error occurred!")
        progress.status_set(TaskState.Error)
        raise e

    progress.pbar_set(prog=100)
    progress.status_set(TaskState.Complete)
    progress.log(f"Found {len(metadata)} songs.")
    progress.log("  NOTE: Metadata covers videos and charts as well!")


def __init_audio_index(progress: TaskProgress):
    csv_path = resource_path("assets/awb.csv")
    print(f"Creating audio index for Reverse 3.07...")

    audio_index.clear()
    with open(csv_path) as f:
        reader = csv.reader(f)
        next(reader)  # skip header

        for row in reader:
            v = awb_index(row[1])
            k = song_id_from_int(int(row[0]))

            audio_index[k] = v
    progress.log(f"Found {len(audio_index)} audio indices.")
    progress.pbar_set(prog=0, maximum=len(audio_index))


def __init_audio_paths(progress: TaskProgress):
    audio_dir = os.path.join(config.working_path, "MER_BGM")
    print(f"Finding audio in {audio_dir}...")

    # untouched files set to figure out which files weren't added
    # used for trying to fix holes in awb.csv
    untouched = set()

    # populate with full-path wav files in audio_dir
    for root, _, files in os.walk(audio_dir):
        for f in files:
            if "wav" in f:
                untouched.add(os.path.join(root, f))

    # populate audio_file with audio_index
    audio_file.clear()
    for k, v in audio_index.items():
        if v is None:
            progress.log(f"WARNING: audio ID {k} has no cue index!!")
            # if k in metadata:
            #     progress.enqueue_log(f"    {metadata[k].name} - {metadata[k].artist}")
            progress.log(f"    This audio ID will have no sound!")
            continue

        f = os.path.join(audio_dir, v[0], f"{v[1]}.wav")
        f_eq = os.path.join(audio_dir, v[0], f"{v[1]+1}.wav")

        if os.path.exists(f):
            if audio_file.get(k) is not None:
                progress.log(
                    f"WARNING: Duplicate audio ID {k}! Overwriting {audio_file[k]} with {f}"
                )

            audio_file[k] = f
            untouched.remove(f)
            untouched.remove(f_eq)
            progress.pbar_set(prog=len(audio_file))
        else:
            progress.log(f"WARNING: Could not find audio for {k} ({f})!")
    progress.log(f"Found {len(audio_file)}/{len(audio_index)} audio files.")

    print(f"{len(untouched)} files weren't added:")
    for f in sorted(untouched):
        print(f"  {f}")


def init_audio(progress: TaskProgress):
    __init_audio_index(progress)
    __init_audio_paths(progress)

    if len(audio_file) < len(audio_index):
        progress.status_set(TaskState.Alert)
    else:
        progress.status_set(TaskState.Complete)

    progress.pbar_set(prog=len(audio_file))


def jackets_progress_task(progress: TaskProgress):
    jackets_present = 0
    for k in metadata:
        if metadata[k].jacket is not None:
            jackets_present += 1
            jacket_preview[k] = Image.open(metadata[k].jacket).resize((200, 200))
        progress.pbar_set(prog=jackets_present, maximum=len(metadata))

    ListingTab.instance.refresh_jacket_previews()
    progress.log(f"Found {jackets_present}/{len(metadata)} jackets.")
    progress.status_set(
        TaskState.Alert if jackets_present < len(metadata) else TaskState.Complete
    )


def _populate_missing():
    missing_audio.clear()
    missing_jackets.clear()

    # populate
    for k in metadata:
        if k not in audio_file:
            missing_audio.append(k)

        if k not in jacket_file:
            missing_jackets.append(k)

    # print
    print(f"Missing audio: {len(missing_audio)}")
    # for k in missing_audio:
    #     s = metadata[k]
    #     print(f"{s.id}: {s.name} - {s.artist}")
    # print()

    print(f"Missing jacket: {len(missing_jackets)}")
    # for k in missing_jackets:
    #     s = metadata[k]
    #     print(f"{s.id}: {s.name} - {s.artist}")
    # print()
