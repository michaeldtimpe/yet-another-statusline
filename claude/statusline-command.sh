#!/usr/bin/env bash
# Claude Code statusLine command

# Do NOT use set -euo pipefail here — the statusLine command runs in a minimal
# environment and any failed subcommand would silently produce no output.
# Instead, use || true / // empty guards throughout.

# Ensure common tool paths are available regardless of how Claude Code
# launches this script
_p="/usr/local/bin:/usr/bin:/bin:${HOME}/.local/bin:${HOME}/bin"
export PATH="${_p}:${PATH:-}"

# Bail out cleanly if jq is not available
if ! command -v jq >/dev/null 2>&1; then
  echo "statusline: jq not found"
  exit 0
fi

input=$(cat)
mkdir -p "$HOME/.claude/statusline-output"
echo "$input" | jq > "$HOME/.claude/statusline-output/statusline.$(date +%s).json"

# ── JSON fields ──────────────────────────────────────────────────────────────
cwd=$(echo "$input"          | jq -r '.cwd')
model=$(echo "$input" | jq -r '.model.display_name // .model.id // "unknown"')
session_id=$(echo "$input"   | jq -r '.session_id // ""')
transcript=$(echo "$input"   | jq -r '.transcript_path // ""')
total_in=$(echo "$input"     | jq -r '.context_window.total_input_tokens // 0')
total_out=$(echo "$input"    | jq -r '.context_window.total_output_tokens // 0')
ctx_used_pct=$(echo "$input" | jq -r '.context_window.used_percentage // empty')

# ── Daily token log ──────────────────────────────────────────────────────────
# Format: YYYY-MM-DD <session_id> <in> <out>
TOKEN_LOG="${HOME}/.claude/statusline-tokens.log"
today=$(date +%Y-%m-%d)

# Write/update this session's entry for today (upsert by session_id)
if [[ -n "$session_id" && ( "$total_in" -gt 0 || "$total_out" -gt 0 ) ]]; then
  # Remove stale entry for this session (if any), then append current
  tmp=$(mktemp)
  grep -v "^[^ ]* ${session_id} " "$TOKEN_LOG" 2>/dev/null > "$tmp" || true
  echo "$today $session_id $total_in $total_out" >> "$tmp"
  mv "$tmp" "$TOKEN_LOG"
fi

# Sum today's tokens across all sessions
day_in=0; day_out=0
while read -r date_ _sid in_ out_; do
  if [[ "$date_" == "$today" ]]; then
    day_in=$(( day_in + in_ ))
    day_out=$(( day_out + out_ ))
  fi
done < <(cat "$TOKEN_LOG" 2>/dev/null)

# ── Session elapsed time ──────────────────────────────────────────────────────
elapsed=""
if [[ -n "$transcript" && -f "$transcript" ]]; then
  start_epoch=$(stat -c %Y "$transcript" 2>/dev/null || echo "")
  if [[ -n "$start_epoch" ]]; then
    now_epoch=$(date +%s)
    secs=$(( now_epoch - start_epoch ))
    h=$(( secs / 3600 ))
    m=$(( (secs % 3600) / 60 ))
    if (( h > 0 )); then
      elapsed="${h}h${m}m"
    else
      elapsed="${m}m"
    fi
  fi
fi

# ── Cost estimate (Bedrock on-demand, ap-southeast-2 region) ─────────────────
# Prices sourced from AWS Bedrock pricing; adjust if model changes.
# Using a conservative blended rate per 1M tokens:
#   claude-sonnet-4:  $3.00/M in,  $15.00/M out
#   claude-haiku-4.5: $0.80/M in,   $4.00/M out
#   claude-opus-4:   $15.00/M in,  $75.00/M out
# We pick rates based on model display name substring matching.
model_lower="${model,,}"
if [[ "$model_lower" == *"opus"* ]]; then
  rate_in=15.00; rate_out=75.00
elif [[ "$model_lower" == *"haiku"* ]]; then
  rate_in=0.80;  rate_out=4.00
else
  # Default: Sonnet
  rate_in=3.00; rate_out=15.00
fi

# Session cost (awk for float math)
session_cost=$(awk -v ti="$total_in" -v to="$total_out" \
  -v ri="$rate_in" -v ro="$rate_out" \
  'BEGIN { printf "%.4f", (ti * ri + to * ro) / 1000000 }')

# Day cost (sum across all model types — approximated using current model rates)
day_cost=$(awk -v ti="$day_in" -v to="$day_out" \
  -v ri="$rate_in" -v ro="$rate_out" \
  'BEGIN { printf "%.4f", (ti * ri + to * ro) / 1000000 }')

# ── Skills list ──────────────────────────────────────────────────────────────
skills=0
skills_names=""

# Find the nearest .claude/skills dir by walking up from cwd.
# Also check workspace.project_dir from the JSON (most reliable for project root).
project_dir=$(echo "$input" | jq -r '.workspace.project_dir // ""')
project_skills_dir=""

# Prefer project_dir from JSON if it has a skills dir
if [[ -n "$project_dir" && -d "$project_dir/.claude/skills" ]]; then
  project_skills_dir="$project_dir/.claude/skills"
else
  # Walk up from cwd looking for a .claude/skills directory
  curr="$cwd"
  while [[ -n "$curr" ]]; do
    if [[ -d "$curr/.claude/skills" ]]; then
      project_skills_dir="$curr/.claude/skills"
      break
    fi
    [[ "$curr" == "/" ]] && break
    curr="${curr%/*}"
  done
fi

# Build list of (group_label, skills_dir) pairs
# Only standalone skills dirs — plugin skills are counted as plugins, not skills
declare -a group_labels=()
declare -a group_dirs=()

# Project .claude/skills/ dirs are managed by plugins — not counted as standalone skills

if [[ -d "${HOME}/.claude/skills" ]]; then
  # group_labels+=("global")
  group_dirs+=("${HOME}/.claude/skills")
fi

# Collect skills per group
declare -A seen_skills
declare -A group_count  # group_label -> count
declare -A group_single # group_label -> single skill name (when count==1)

_add_skill() {
  local label="$1" name="$2"
  [[ -n "${seen_skills[$name]+x}" ]] && return
  seen_skills[$name]=1
  skills=$(( skills + 1 ))
  group_count[$label]=$(( ${group_count[$label]:-0} + 1 ))
  group_single[$label]="$name"
}

for i in "${!group_labels[@]}"; do
  label="${group_labels[$i]}"
  skills_dir="${group_dirs[$i]}"
  [[ -d "$skills_dir" ]] || continue
  # Style 1: subdirectory with SKILL.md inside
  while IFS= read -r skill_dir; do
    _add_skill "$label" "$(basename "$skill_dir")"
  done < <(find "$skills_dir" -mindepth 1 -maxdepth 1 -type d 2>/dev/null \
    | while IFS= read -r d; do [[ -f "$d/SKILL.md" ]] && echo "$d"; done | sort)
  # Style 2: flat *.md files
  while IFS= read -r f; do
    _add_skill "$label" "$(basename "$f" .md)"
  done < <(find "$skills_dir" -maxdepth 1 -name '*.md' ! -name 'SKILL.md' 2>/dev/null | sort)
done

# Build display string: group(N) if >1, else skill name; skip generic labels
skills_names=""
declare -A seen_labels
for label in "${group_labels[@]}"; do
  [[ -n "${seen_labels[$label]+x}" ]] && continue
  seen_labels[$label]=1
  cnt="${group_count[$label]:-0}"
  (( cnt == 0 )) && continue
  if (( cnt > 1 )); then
    token="${label}(${cnt})"
  else
    token="${group_single[$label]}"
  fi
  skills_names="${skills_names:+$skills_names,}$token"
done

# ── Plugin names ─────────────────────────────────────────────────────────────
plugin_names=""
declare -A seen_plugins
for settings_file in "${HOME}/.claude/settings.json" "$project_dir/.claude/settings.json"; do
  [[ -f "$settings_file" ]] || continue
  while IFS= read -r plugin_key; do
    [[ -n "${seen_plugins[$plugin_key]+x}" ]] && continue
    seen_plugins[$plugin_key]=1
    pname="${plugin_key%%@*}"
    plugin_names="${plugin_names:+$plugin_names,}$pname"
  done < <(jq -r '.enabledPlugins // {} | to_entries[] | select(.value == true) | .key' "$settings_file" 2>/dev/null)
done

# ── Git detection (no optional locks) ────────────────────────────────────────
git_branch=""; git_commit=""; repo=""; gitdir=""
curr="$cwd"
while [[ -n "$curr" ]]; do
  if [[ -e "$curr/.git" ]]; then
    repo="$curr"; gitdir="$curr/.git"; break
  fi
  curr="${curr%/*}"
done

if [[ -n "${repo:-}" && -f "$gitdir/HEAD" ]]; then
  read -r head < "$gitdir/HEAD"
  case "$head" in
    ref:*) git_branch="${head##*/}" ;;
    "")    git_branch="" ;;
    *)     git_branch="d:${head:0:7}" ;;
  esac
  if [[ -n "$git_branch" && -f "$gitdir/refs/heads/$git_branch" ]]; then
    read -r commit < "$gitdir/refs/heads/$git_branch"
    git_commit="${commit:0:9}"
  elif [[ -f "$gitdir/ORIG_HEAD" ]]; then
    read -r commit < "$gitdir/ORIG_HEAD"
    git_commit="${commit:0:9}"
  fi
fi

# ── OpenSpec progress bar ─────────────────────────────────────────────────────
# Look for openspec directories anywhere up the tree from cwd
openspec_bar=""
openspec_root=""
curr="$cwd"
while [[ -n "$curr" ]]; do
  if [[ -d "$curr/openspec" ]]; then
    openspec_root="$curr/openspec"; break
  fi
  curr="${curr%/*}"
done

declare -a openspec_names=()
declare -a openspec_done=()
declare -a openspec_total=()

if [[ -n "$openspec_root" ]]; then
  while IFS= read -r f; do
    change_name=$(basename "$(dirname "$f")")
    t=$(grep -c '^\s*- \[ \]' "$f" 2>/dev/null || true)
    d=$(grep -c '^\s*- \[x\]' "$f" 2>/dev/null || true)
    total=$(( t + d ))
    (( total == 0 )) && continue
    openspec_names+=("\e[3m$change_name\e[0m")
    openspec_done+=("$d")
    openspec_total+=("$total")
  done < <(find "$openspec_root" -name 'tasks.md' -not -path '*/archive/*' 2>/dev/null | sort)
fi

# ── Short pwd ─────────────────────────────────────────────────────────────────
short=$(sed 's:\([^/]\)[^/]*/:\1/:g' <<< "${cwd/#$HOME/\~}")

# ── Assemble output ───────────────────────────────────────────────────────────
# Line 1: pwd | branch/commit | session id
# Line 2: model [| skill names]
# Line 3: session & daily stats (time, tokens, cost)
# Line 4: openspec progress bar (omitted when no openspec)

# Colour helpers (ANSI)
c_reset='\033[0m'
c_pwd='\033[38;5;75m'       # blue — path
c_branch='\033[38;5;114m'   # green — branch
c_commit='\033[38;5;244m'   # grey — commit hash
c_dirty='\033[38;5;214m'    # orange — modified/untracked
c_session='\033[38;5;244m'  # grey — session id
c_model='\033[38;5;183m'    # lavender — model name
c_skills='\033[38;5;222m'   # yellow — skills count
c_time='\033[38;5;244m'     # grey — time
c_tok='\033[38;5;116m'      # cyan — tokens
c_cost='\033[38;5;210m'     # salmon — cost
c_bar_fill='\033[38;5;114m' # green — filled bar blocks
c_bar_empty='\033[38;5;238m' # dark grey — empty bar blocks
c_label='\033[38;5;244m'    # grey — labels/punctuation
c_ctx='\033[38;5;216m'      # peach — context usage %

time_str=$(date +%T)
sid="${session_id}"

# Format token counts (K suffix)
fmt_tok() {
  local n=$1
  if (( n >= 1000 )); then
    awk -v n="$n" 'BEGIN { printf "%.1fK", n/1000 }'
  else
    echo "$n"
  fi
}

total_in_fmt=$(fmt_tok "$total_in")
total_out_fmt=$(fmt_tok "$total_out")
day_in_fmt=$(fmt_tok "$day_in")
day_out_fmt=$(fmt_tok "$day_out")

# ── Line 1: repo path | branch/commit | session id ───────────────────────────
line1="${c_pwd}${short}${c_reset}"

if [[ -n "$git_branch" ]]; then
  modified=""; untracked=""
  git -C "$repo" ls-files -m --no-optional-locks 2>/dev/null \
    | grep -q . && modified="${c_dirty}✹${c_reset}"
  git -C "$repo" ls-files --others --exclude-standard \
    --directory --no-empty-directory --error-unmatch \
    --no-optional-locks -- ':/*' 2>/dev/null \
    | grep -q . && untracked="${c_dirty}✭${c_reset}"
  line1+=" ${c_label}∈${c_reset}"
  line1+=" ${c_branch}${git_branch}${c_reset}"
  line1+="${c_label}/${c_reset}"
  line1+="${c_commit}${git_commit}${c_reset}"
  line1+="${modified}${untracked}"
fi

[[ -n "$sid" ]] && \
  line1+=" ${c_session}[${sid}]${c_reset}"

# ── Line 2: model [| skills] [| plugins] ─────────────────────────────────────
line2="${c_model}💻 ${model}${c_reset}"
if (( skills > 0 )); then
  line2+=" ${c_label}|${c_reset}"
  line2+=" [${c_skills}${skills_names}${c_reset}]"
fi
if [[ -n "$ctx_used_pct" ]]; then
  ctx_used_fmt=$(printf "%.0f" "$ctx_used_pct")
  line2+=" ${c_label}|${c_reset}"
  line2+=" ${c_label}⏳${c_reset}${c_ctx}${ctx_used_fmt}%${c_reset}"
fi
if [[ -n "$plugin_names" ]]; then
  line2+=" ${c_label}|${c_reset}"
  line2+=" ${c_skills}${plugin_names}${c_reset}"
fi

# ── Line 3: time | tokens | cost ─────────────────────────────────────────────
line3="${c_time}${time_str}${c_reset}"
[[ -n "$elapsed" ]] && \
  line3+="${c_label}(+${elapsed})${c_reset}"
line3+=" ⬙ ${c_label}↓${c_reset}${c_tok}${total_in_fmt}${c_reset}"
line3+="${c_label} ↑${c_reset}${c_tok}${total_out_fmt}${c_reset}"
if [[ "$day_in_fmt" != "$total_in_fmt" || "$day_out_fmt" != "$total_out_fmt" ]]; then
  line3+=" / ${c_label}↓${c_reset}${c_tok}${day_in_fmt}${c_reset}"
  line3+="${c_label} ↑${c_reset}${c_tok}${day_out_fmt}${c_reset}"
fi
line3+=" 💰 ${c_cost}\$${session_cost}${c_reset}"
if [[ "$day_cost" != "$session_cost" ]]; then
  line3+="${c_label}/${c_reset}${c_cost}\$${day_cost}${c_reset}"
fi

# ── Line 4+: openspec bars (coloured, one per change) ────────────────────────
openspec_lines=""
for idx in "${!openspec_names[@]}"; do
  name="${openspec_names[$idx]}"
  d="${openspec_done[$idx]}"
  t="${openspec_total[$idx]}"
  bar_width=30
  filled=$(( d * bar_width / t ))
  bar_filled=""; bar_empty=""
  for (( i=0; i<bar_width; i++ )); do
    (( i < filled )) && bar_filled+="█" || bar_empty+="░"
  done
  pct=$(( d * 100 / t ))
  ratio=$(printf "%d/%d" "$d" "$t")
  pct_str=$(printf "%3d" "$pct")
  line="${c_bar_fill}${bar_filled}${c_reset}"
  line+="${c_bar_empty}${bar_empty}${c_reset}"
  line+=" ${c_label}${ratio}${c_reset} \033[1m${pct_str}%\033[0m"
  line+=" ${c_label}${name}${c_reset}"
  openspec_lines+=$'\n'"${line}"
done

# ── Assemble ──────────────────────────────────────────────────────────────────
out="${line1}
${line2}
${line3}"

[[ -n "$openspec_lines" ]] && out+="${openspec_lines}"

printf '%b' "$out"
