import pyglet
import os

# Path to the audio file. Make sure you have an 'audio.wav' in the same directory as this script.
audio_file_path = 'audio.wav'

if not os.path.exists(audio_file_path):
    print(f"Error: Audio file '{audio_file_path}' not found.")
    print("Please place an audio file (e.g., .wav, .mp3) named 'audio.wav' in the same directory as this script.")
    pyglet.app.exit()
else:
    try:
        music = pyglet.media.load(audio_file_path)
        player = pyglet.media.Player()
        player.queue(music)
        player.play()

        print(f"Playing '{audio_file_path}'. Press Ctrl+C to stop.")

        # Keep the application running until the sound finishes or is stopped
        pyglet.app.run()

    except pyglet.media.MediaException as e:
        print(f"Error loading or playing audio: {e}")
        print("Ensure you have the necessary codecs installed for your audio file type.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")