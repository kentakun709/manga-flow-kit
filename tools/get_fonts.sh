#!/bin/bash
# 黒帯（場面転換の帯）の文字に使うフォントを取る。どちらも OFL（無料・商用可）。
# 使い方: キットの一番上で  bash tools/get_fonts.sh
# fonts/ は git に載せない。無くても動く（その時はパソコンに入っている日本語フォントを使う）。
cd "$(dirname "$0")/.." && mkdir -p fonts
B="https://raw.githubusercontent.com/google/fonts/main/ofl"
curl -sL -o fonts/ShipporiAntiqueB1-Regular.ttf "$B/shipporiantiqueb1/ShipporiAntiqueB1-Regular.ttf"  # アンチック体
curl -sL -o fonts/ZenAntique-Regular.ttf        "$B/zenantique/ZenAntique-Regular.ttf"                # アンチック体（予備）
ls -la fonts/
