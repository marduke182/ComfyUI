#!/usr/bin/env bash
# Live ComfyUI model-download progress.  Watch:  watch -n 5 bash ~/apps/ComfyUI/dlprogress.sh
cd /home/jquintana/apps/ComfyUI || exit
if pgrep -f hf_dl.py >/dev/null; then echo "downloader: RUNNING"; else echo "downloader: STOPPED"; fi
echo "------------------------------------------"
inc=$(find .hf_tmp -name "*.incomplete" 2>/dev/null | head -1)
incsz=0; [ -n "$inc" ] && incsz=$(stat -c%s "$inc" 2>/dev/null || echo 0)
row() { # path target_bytes label
  local s; s=$(stat -c%s "$1" 2>/dev/null || echo 0)
  # if final file is empty but a temp chunk is in flight, show the temp chunk for this (in-progress) file
  [ "$s" -lt 1000000 ] && [ "$incsz" -gt 1000000 ] && s=$incsz
  printf "[%3d%%] %-16s %5d / %5d MB\n" "$(( s*100/$2 ))" "$3" "$((s/1048576))" "$(($2/1048576))"
}
row models/ipadapter/ip-adapter-plus_sdxl_vit-h.safetensors          847517512  "ip-adapter"
row models/clip_vision/CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors  2528373448  "CLIP-ViT-H"
row models/checkpoints/ace_step_v1_3.5b.safetensors                 7699743341  "ace_step(audio)"
