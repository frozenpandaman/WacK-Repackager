import os
import re
import json
from metadata import Difficulty, SongMetadata

jackets_dir = "./data/jackets"
'''
Path to folder which contains song jackets.
'''

charts_dir = "./data/MusicData"
'''
Path to folder which contains charts.

Folder should only contain song ID-named folders, each of which contain .mer files.
This is how it's stored in WACCA's files (MusicData).
'''

audio_dir = "./data/MER_BGM"
'''
Path to folder which contains music audio.
'''

# ID to song metadata
metadata: dict[str, SongMetadata] = dict()

# ID to audio path
audio_file: dict[str, str] = dict()

# ID to jacket path 
jacket_file: dict[str, str] = dict()

def init():
	__init_songs()
	__init_audio_paths()
	__init_jacket_paths()

def __init_songs():
	print('Initializing charts metadata...')
	metadata.clear()
	md_json: list
	with open("./data/metadata.json", "r", encoding='utf_8') as read_file:
		md_json = json.load(read_file)['Exports'][0]["Table"]["Data"]
	
	for elem in md_json: # songs
		id: str
		genre: int
		name: str
		artist: str
		copyright: str
		tempo: str
		audio_preview: str
		audio_preview_len: str
		levels: list[str] = [None, None, None, None]
		level_audio: list[str] = [None, None, None, None] # from .mer
		level_designer: list[str] = [None, None, None, None]
		level_clear_requirements: list[str] = [None, None, None, None]

		# MusicParameterTable JSON parsing
		for key in elem['Value']: # properties of song
			if key['Name'] == 'AssetDirectory':
				id = key['Value']
			#SongInfo
			if key['Name'] == 'ScoreGenre':
				genre = int(key['Value'])
			if key['Name'] == 'MusicMessage':
				name = key['Value']
			if key['Name'] == 'ArtistMessage':
				artist = key['Value']
			if key['Name'] == 'Bpm':
				tempo = key['Value']
			if key['Name'] == 'CopyrightMessage':
				copyright = key['Value']
			#ChartInfo Levels; "+0" = no chart
			if key['Name'] == 'DifficultyNormalLv':
				levels[0] = key['Value']
			if key['Name'] == 'DifficultyHardLv':
				levels[1] = key['Value']
			if key['Name'] == 'DifficultyExtremeLv':
				levels[2] = key['Value']
			if key['Name'] == 'DifficultyInfernoLv':
				levels[3] = key['Value']
			#Audio Previews
			if key['Name'] == 'PreviewBeginTime':
				audio_preview = key['Value']
			if key['Name'] == 'PreviewSeconds':
				audio_preview_len = key['Value']
			#Clear Requirements
			if key['Name'] == 'ClearNormaRateNormal':
				level_clear_requirements[0] = key['Value']
			if key['Name'] == 'ClearNormaRateHard':
				level_clear_requirements[1] = key['Value']
			if key['Name'] == 'ClearNormaRateExpert':
				level_clear_requirements[2] = key['Value']
			if key['Name'] == 'ClearNormaRateInferno':
				level_clear_requirements[3] = key['Value']
			#ChartInfo Designers
			if key['Name'] == 'NotesDesignerNormal':
				level_designer[0] = key['Value']
			if key['Name'] == 'NotesDesignerHard':
				level_designer[1] = key['Value']
			if key['Name'] == 'NotesDesignerExpert':
				level_designer[2] = key['Value']
			if key['Name'] == 'NotesDesignerInferno':
				level_designer[3] = key['Value']

		# print(f'{id}: {name} - {artist}')
		if 'S99' in id:
			# print('Skipping system song...')
			continue

		# mer difficulty-audio IDs
		mer_dir = f'{charts_dir}/{id}'
		for root, _, files in os.walk(f'{mer_dir}'):
			for f in files:
				diff_idx = int(re.search(r"\d\d.mer", f).group()[:2])

				lines: list[str]
				with open(f'{root}/{f}', 'r') as chf:
					lines = chf.readlines()
				a_id = None
				offset = None
				for l in lines:
					if "MUSIC_FILE_PATH" in l:
						a_id = re.search(r"S\d\d_\d\d\d", l.split()[1]).group()
					elif "OFFSET" in l:
						offset = l.split()[1]
					if a_id and offset: break

				level_audio[diff_idx] = (a_id, offset)

		# difficulty iteration -- level_audio has None for diffs w/o chart
		difficulties: list[Difficulty] = [None, None, None, None]
		for i, audio in enumerate(level_audio):
			if audio is None: continue
			difficulties[i] = Difficulty (
				audio_id=audio[0],
				audio_offset=audio[1],
				audio_preview_time=audio_preview,
				audio_preview_length=audio_preview_len,
				designer=level_designer[i],
				clearRequirement=level_clear_requirements[i],
				diffLevel=levels[i]
			)
		metadata[id] = SongMetadata(
			id=id,
			name=name,
			artist=artist,
			genre_id=genre,
			copyright=copyright,
			tempo=tempo,
			difficulties=difficulties
		)

def __init_audio_paths():
	print(f'Finding audio in {audio_dir}')
	for root, _, files in os.walk(audio_dir):
		for f in files:
			m = re.search(r"S\d\d_\d\d\d", f)
			if m is None: continue
			
			id = m.group()
			if id in audio_file:
				# lexicographically smaller file has proper audio
				audio_file[id] = min(audio_file[id], f)
			else:
				audio_file[id] = f
			print(f'{id} = {audio_file[id]}')

def __init_jacket_paths():
	print(f'Finding jackets in {jackets_dir}')
	for root, _, files in os.walk(jackets_dir):
		for f in files:
			m = re.search(r'S\d\d-\d\d\d', f)
			if m is None: continue
			jacket_file[m.group()] = f
			print(f'{m.group()} = {f}')
