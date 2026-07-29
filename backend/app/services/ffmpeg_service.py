import os
import asyncio
import ffmpeg
from fractions import Fraction
from app.config import settings

def get_video_metadata(file_path: str) -> dict:
    """Extract metadata using ffprobe."""
    try:
        probe = ffmpeg.probe(file_path, cmd=settings.FFPROBE_PATH)
        video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
        
        if not video_stream:
            return {}

        # Safe FPS parsing (avoid eval for security)
        fps_str = video_stream.get('r_frame_rate', '0/1')
        try:
            fps = float(Fraction(fps_str))
        except (ValueError, ZeroDivisionError):
            fps = 0.0

        return {
            "duration": float(probe['format'].get('duration', 0)),
            "width": int(video_stream.get('width', 0)),
            "height": int(video_stream.get('height', 0)),
            "fps": fps,
            "codec": video_stream.get('codec_name', ''),
            "bitrate": int(probe['format'].get('bit_rate', 0))
        }
    except ffmpeg.Error as e:
        print(f"FFprobe error: {e.stderr.decode() if e.stderr else str(e)}")
        return {}

async def trim_video(input_path: str, output_path: str, start_time: float, end_time: float) -> str:
    """Trim a video asynchronously with timeout."""
    duration = end_time - start_time
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    try:
        args = [
            settings.FFMPEG_PATH,
            '-y',
            '-ss', str(start_time),
            '-i', input_path,
            '-t', str(duration),
            '-c', 'copy',
            output_path
        ]

        import subprocess as _subprocess

        def _run():
            proc = _subprocess.Popen(args, stdout=_subprocess.PIPE, stderr=_subprocess.PIPE)
            try:
                out_data, err_data = proc.communicate(timeout=120)
                return proc.returncode, out_data, err_data
            except _subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate()
                raise Exception("FFmpeg trim timed out after 120 seconds")

        returncode, _, err_data = await asyncio.to_thread(_run)
        if returncode != 0:
            err_text = err_data.decode('utf-8', errors='replace') if err_data else 'Unknown FFmpeg error'
            raise Exception(f"FFmpeg error (code {returncode}): {err_text}")
        return output_path
    except Exception as e:
        raise Exception(f"Failed to trim video: {str(e)}")

import re

async def detect_silence(input_path: str, threshold_db: int = -30, duration: float = 0.5) -> list[dict]:
    """Detect silent parts in a video."""
    try:
        process = (
            ffmpeg
            .input(input_path)
            .filter('silencedetect', n=f'{threshold_db}dB', d=duration)
            .output('null', f='null')
            .run_async(cmd=settings.FFMPEG_PATH, pipe_stdout=True, pipe_stderr=True)
        )
        out, err = await asyncio.to_thread(process.communicate)
        err_str = err.decode()
        
        silences = []
        current_start = None
        
        for line in err_str.split('\n'):
            if 'silence_start:' in line:
                match = re.search(r'silence_start:\s*([\d\.]+)', line)
                if match:
                    current_start = float(match.group(1))
            elif 'silence_end:' in line:
                match = re.search(r'silence_end:\s*([\d\.]+)', line)
                if match and current_start is not None:
                    silences.append({
                        "start": current_start,
                        "end": float(match.group(1))
                    })
                    current_start = None
                    
        return silences
    except Exception as e:
        raise Exception(f"Failed to detect silence: {str(e)}")

async def auto_trim_video(input_path: str, output_path: str, threshold_db: int = -30) -> str:
    """Trim initial and ending silence from video."""
    silences = await detect_silence(input_path, threshold_db)
    
    start_time = 0.0
    if silences and silences[0]['start'] < 1.0:
        start_time = silences[0]['end']
        
    metadata = get_video_metadata(input_path)
    end_time = metadata.get('duration', 0)
    
    if silences and end_time > 0:
        last_silence = silences[-1]
        if last_silence['end'] >= end_time - 1.0:
             end_time = last_silence['start']
             
    if start_time == 0.0 and (end_time == metadata.get('duration', 0) or end_time == 0):
        import shutil
        await asyncio.to_thread(shutil.copy, input_path, output_path)
        return output_path

    return await trim_video(input_path, output_path, start_time, end_time)

async def merge_videos(input_paths: list[str], output_path: str) -> str:
    """Merge multiple videos sequentially (assumes same format/resolution)."""
    # Write a concat file
    list_path = os.path.join(settings.TEMP_DIR, f"concat_list_{os.path.basename(output_path)}.txt")
    with open(list_path, "w") as f:
        for path in input_paths:
            # absolute path formatting for ffmpeg concat demuxer
            f.write(f"file '{os.path.abspath(path)}'\n")
    
    try:
        process = (
            ffmpeg
            .input(list_path, format='concat', safe=0)
            .output(output_path, c="copy")
            .overwrite_output()
            .run_async(cmd=settings.FFMPEG_PATH, pipe_stdout=True, pipe_stderr=True)
        )
        out, err = await asyncio.to_thread(process.communicate)
        if process.returncode != 0:
            raise Exception(f"FFmpeg error: {err.decode()}")
        return output_path
    except Exception as e:
        raise Exception(f"Failed to merge videos: {str(e)}")
    finally:
        if os.path.exists(list_path):
            os.remove(list_path)

async def extract_audio(input_path: str, output_path: str) -> str:
    """Extract audio from video as MP3 or PCM WAV with vocal clarity filters for transcription."""
    try:
        if output_path.lower().endswith('.wav'):
            process = (
                ffmpeg
                .input(input_path)
                .filter('highpass', f=80)
                .filter('lowpass', f=7500)
                .filter('loudnorm')
                .output(output_path, acodec='pcm_s16le', ar=16000, ac=1)
                .overwrite_output()
                .run_async(cmd=settings.FFMPEG_PATH, pipe_stdout=True, pipe_stderr=True)
            )
        else:
            process = (
                ffmpeg
                .input(input_path)
                .filter('loudnorm')
                .output(output_path, acodec='libmp3lame', q=4)
                .overwrite_output()
                .run_async(cmd=settings.FFMPEG_PATH, pipe_stdout=True, pipe_stderr=True)
            )
        out, err = await asyncio.to_thread(process.communicate)
        if process.returncode != 0:
            raise Exception(f"FFmpeg error: {err.decode()}")
        return output_path
    except Exception as e:
         raise Exception(f"Failed to extract audio: {str(e)}")

async def burn_subtitles(video_path: str, subtitle_path: str, output_path: str) -> str:
    """Burn SRT subtitles into a video with modern styled lower-third captions."""
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        os.makedirs(os.path.dirname(subtitle_path), exist_ok=True)

        # Build sub_path for filter: forward slashes, escape single quotes
        abs_sub = os.path.abspath(subtitle_path)
        sub_for_filter = abs_sub.replace('\\', '/').replace("'", "\\'")

        style_opts = "FontSize=20,FontName=Arial,Bold=1,PrimaryColour=&H00FFFF,BackColour=&H80000000,BorderStyle=4,MarginV=25"
        filter_str = f"subtitles='{sub_for_filter}':force_style='{style_opts}'"

        args = [
            settings.FFMPEG_PATH,
            '-y',
            '-i', video_path,
            '-c:v', 'libx264',
            '-c:a', 'copy',
            '-preset', 'ultrafast',
            '-vf', filter_str,
            output_path
        ]

        import subprocess as _subprocess

        def _run():
            proc = _subprocess.Popen(args, stdout=_subprocess.PIPE, stderr=_subprocess.PIPE)
            try:
                out_data, err_data = proc.communicate(timeout=600)
                return proc.returncode, out_data, err_data
            except _subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate()
                raise Exception("FFmpeg burn subtitles timed out after 600 seconds")

        returncode, _, err_data = await asyncio.to_thread(_run)
        if returncode != 0:
            err_text = err_data.decode('utf-8', errors='replace') if err_data else 'Unknown FFmpeg error'
            raise Exception(f"FFmpeg error (code {returncode}): {err_text}")
        return output_path
    except Exception as e:
         raise Exception(f"Failed to burn subtitles: {str(e)}")

async def burn_subtitles_and_broll_overlay(video_path: str, subtitle_path: str, broll_path: str, start_time: float, end_time: float, output_path: str, width: int = 1280, height: int = 720) -> str:
    """Scale B-roll footage to cover main video frame aspect ratio without letterbox bars and burn subtitles."""
    try:
        # Build sub_path for filter: forward slashes, escape single quotes
        abs_sub = os.path.abspath(subtitle_path)
        sub_for_filter = abs_sub.replace('\\', '/').replace("'", "\\'")

        style_opts = "FontSize=20,FontName=Arial,Bold=1,PrimaryColour=&H00FFFF,BackColour=&H80000000,BorderStyle=4,MarginV=25"

        filter_graph = (
            f"[1:v] scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height} [broll_scaled];"
            f"[0:v][broll_scaled] overlay=0:0:enable='between(t,{start_time},{end_time})' [v_overlay];"
            f"[v_overlay] subtitles='{sub_for_filter}':force_style='{style_opts}' [outv]"
        )

        in_main = ffmpeg.input(video_path)
        in_broll = ffmpeg.input(broll_path)

        process = (
            ffmpeg
            .output(in_main['a?'], in_main, in_broll, output_path, filter_complex=filter_graph, map='[outv]')
            .overwrite_output()
            .run_async(cmd=settings.FFMPEG_PATH, pipe_stdout=True, pipe_stderr=True)
        )
        out, err = await asyncio.to_thread(process.communicate)
        if process.returncode != 0:
            return await burn_subtitles(video_path, subtitle_path, output_path)
        return output_path
    except Exception as e:
        print(f"B-roll overlay hardcoding fallback: {e}")
        return await burn_subtitles(video_path, subtitle_path, output_path)
