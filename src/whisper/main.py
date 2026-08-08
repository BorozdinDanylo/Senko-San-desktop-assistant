from pathlib import Path
from faster_whisper import WhisperModel


audio_path = Path("./media/SenkoSanVoice.wav")

model = WhisperModel(
    "large-v3",
    device="cuda",
    compute_type="float16",
)

prompt = """
今日はいい天気じゃのう。
朝食の準備も捗るというものじゃ。
これで準備も終わったかな。
そろそろあやつを起こさねばな。
いつもながら可愛い寝顔じゃ。
このまま寝かせておいてやりたいが、
なるべく優しく起こしてやるからな。
ほれ、お主よ。朝じゃぞ。
どうじゃ、起きられるかな。
起きぬか。
もう少し強く揺するしかあるまい。
お主よ。
起きぬと遅刻してしまうぞ。
おいしい朝ごはんも用意したのじゃぞ。
ちょっと頑張って起きてみぬかの。
これは強敵じゃ。
これほど疲れておるのなら、
いっそ会社とやらがなくなってしまえばよいのじゃが、
そうもいかんからの。
お主よ。
"""

segments, info = model.transcribe(
    str(audio_path),
    language="ja",

    beam_size=10,
    word_timestamps=True,

    initial_prompt=prompt,

    condition_on_previous_text=True,
    vad_filter=False,
)


for segment in segments:
    print(
        f"\nSEGMENT [{segment.start:.2f} -> {segment.end:.2f}] "
        f"{segment.text}"
    )

    for word in segment.words or []:
        print(
            f"    [{word.start:.2f} -> {word.end:.2f}] "
            f"{word.word}"
        )
