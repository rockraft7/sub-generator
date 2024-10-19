import subprocess
import os
import azure.cognitiveservices.speech as speechsdk
import requests
import datetime
import json
from pydub import AudioSegment  # Install pydub via pip
import threading
import time

# Step 0: Extract and convert audio to 16kHz mono using FFmpeg
def extract_and_convert_audio(input_video, output_wav):
    """Extracts audio from video and converts it to 16kHz mono using FFmpeg."""
    temp_wav = "temp_audio.wav"  # Temporary file for initial extraction
    try:
        # Step 1: Extract audio from video
        extract_command = ["ffmpeg", "-i", input_video, "-af", "afftdn", temp_wav]
        subprocess.run(extract_command, check=True)
        print(f"Audio extracted from {input_video} and saved as {temp_wav}")

        # Step 2: Convert audio to 16kHz mono
        convert_command = ["ffmpeg", "-i", temp_wav, "-ac", "1", "-ar", "16000", output_wav]
        subprocess.run(convert_command, check=True)
        print(f"Audio converted to 16kHz mono and saved as {output_wav}")

        # Remove the temporary WAV file
        if os.path.exists(temp_wav):
            os.remove(temp_wav)
    except subprocess.CalledProcessError as e:
        print(f"Error processing audio: {e}")
        raise

# Step 1: Trim the audio
def trim_audio(audio_file, start_time, end_time, output_file="trimmed_audio.wav"):
    """Trim the audio file to the specified timeframe."""
    audio = AudioSegment.from_wav(audio_file)
    trimmed_audio = audio[start_time * 1000:end_time * 1000]  # Time in milliseconds
    trimmed_audio.export(output_file, format="wav")
    return output_file

def get_audio_duration(audio_file):
    """Get the duration of the audio file in seconds."""
    audio = AudioSegment.from_wav(audio_file)
    return len(audio) / 1000  # Convert to seconds

def seconds_to_timestamp(seconds):
    """Convert seconds to HH:MM:SS,ms format for SRT."""
    t = str(datetime.timedelta(seconds=seconds))
    
    # Initialize hours, minutes, seconds, and milliseconds
    hours, minutes, seconds, ms = "00", "00", "00", "000"
    
    try:
        # Split based on whether milliseconds are present
        if "." in t:
            time_part, ms = t.split(".")
            ms = ms[:3]  # Limit to 3 digits for milliseconds
        else:
            time_part = t
        
        # Split the time part into hours, minutes, and seconds
        hours, minutes, seconds = time_part.split(":")
    except Exception as e:
        print(f"Error parsing time: {e}")

    # Ensure all parts are properly zero-padded
    return f"{hours.zfill(2)}:{minutes.zfill(2)}:{seconds.zfill(2)},{ms.zfill(3)}"

def generate_srt(transcription, output_file="subtitles.srt"):
    """Generate an SRT file from the transcription."""
    with open(output_file, "w") as f:
        for i, result in enumerate(transcription, 1):
            start_time = seconds_to_timestamp(result['start'])
            end_time = seconds_to_timestamp(result['end'])
            f.write(f"{i}\n")
            f.write(f"{start_time} --> {end_time}\n")
            f.write(f"{result['text']}\n\n")

# Step 2: Speech-to-Text (Cantonese)
def speech_to_text(audio_file, language='zh-HK'):
    """Transcribe the speech from a long audio file."""
    speech_key = os.getenv("SPEECH_KEY")
    service_region = "eastus"
    speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)
    speech_config.speech_recognition_language = language
    audio_config = speechsdk.audio.AudioConfig(filename=audio_file)

    recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

    all_results = []
    done = threading.Event()

    def handle_final_result(evt):
        """Handle each recognized segment."""
        all_results.append({
            'text': evt.result.text,
            'start': evt.result.offset / 10**7,  # Convert ticks to seconds
            'end': (evt.result.offset + evt.result.duration) / 10**7
        })
        print(f"Recognized: {evt.result.text}")

    def stop_recognition(evt):
        """Stop recognition when all results are processed."""
        print(f"Stopping recognition as final result received: {evt}")
        recognizer.stop_continuous_recognition()
        if evt.result.cancellation_details:
            print(f"Cancellation: {evt.result.cancellation_details}")
            if evt.result.cancellation_details.error_details:
                print(f"Error details: {evt.result.cancellation_details.error_details}")
        done.set()  # Signal that recognition is done

    # Connect event handler for recognized events
    recognizer.recognized.connect(handle_final_result)

    # Connect event handler to stop recognition on completion
    recognizer.session_stopped.connect(stop_recognition)
    recognizer.canceled.connect(stop_recognition)

    # Start continuous recognition
    recognizer.start_continuous_recognition()
    print("Recognizing...")

    # Wait for the recognizer to finish processing
    done.wait()  # Wait until recognition is done

    return all_results

# Step 3: Translate Cantonese to English
def translate_text(text, from_lang='zh-Hant', to_lang='en'):
    """Translate text from Cantonese to English using Azure Translator."""
    subscription_key = os.getenv("TRANSLATOR_KEY")
    endpoint = "https://api.cognitive.microsofttranslator.com/translate?api-version=3.0"
    headers = {
        'Ocp-Apim-Subscription-Key': subscription_key,
        'Content-Type': 'application/json',
        'Ocp-Apim-Subscription-Region': 'eastus',
    }
    params = {
        'from': from_lang,
        'to': to_lang
    }
    body = [{
        'text': text
    }]
    response = requests.post(endpoint, params=params, headers=headers, json=body)
    translation = response.json()[0]['translations'][0]['text']
    return translation

# Step 4: Speech to SRT with Translation
def speech_to_srt_with_translation(video_file, start_time=None, end_time=None):
    """Transcribe the audio file, translate, and generate an SRT file."""
    base_path = video_file.rsplit(".", 1)[0]
    audio_file = base_path + ".wav"
    
    # Step 0: Extract and convert audio to 16kHz mono using FFmpeg
    if not os.path.exists(audio_file):
        extract_and_convert_audio(video_file, audio_file)

    original_audio_file = audio_file
    # Trim audio if a start_time and end_time are specified
    if start_time is not None and end_time is not None:
        audio_file = trim_audio(audio_file, start_time, end_time)

    # Transcribe the audio file
    if not os.path.exists("results.json"):
        transcription_result = speech_to_text(audio_file)
        with open("results.json", "w") as f:
            json.dump(transcription_result, f, indent=2)  # Pretty-print with indentation
    else:
        with open("results.json", "r") as f:
            transcription_result = json.load(f)  # Load the saved transcription

    # Translate each segment and update the transcription with translated text
    if not os.path.exists("translated.json"):
        for segment in transcription_result:
            translated_text = translate_text(segment['text'])
            segment['text'] = translated_text
        with open("translated.json", "w") as f:
            json.dump(transcription_result, f, indent=2)
    else:
        with open("translated.json", "r") as f:
            transcription_result = json.load(f)

    generate_srt(transcription_result, output_file=f"{base_path}.srt")
    if os.path.exists("results.json"):
        os.remove("results.json")
    if os.path.exists("translated.json"):
        os.remove("translated.json")
    if os.path.exists(audio_file):
        os.remove(audio_file)
    if os.path.exists(original_audio_file):
        os.remove(original_audio_file)
    

# Example usage
video_file = "/workspaces/videos/02.ts"
start_time = 600  # Start at 10 minutes (600 seconds)
end_time = 720   # End at 12 minutes (720 seconds)

# Call the function with a specific timeframe
#speech_to_srt_with_translation(video_file, audio_file, start_time, end_time)

start = time.time()
speech_to_srt_with_translation(video_file)
end = time.time()
print(f"Subtitle generated in {int((end - start) / 60)} minutes and {int((end - start) % 60)} seconds")