#!/bin/sh
# SessionStart hook for a Cowork Remote session that began as a claude.ai chat.
# Links four Anthropic skills that the skills sync does not deliver from the
# mounted catalogue into Claude Code's user skills directory, <config dir>/skills.

# Claude Code waits for this script before it reads the session's first
# message, so start a program only when there is a link to make or remove.

# Drain the hook's JSON input. Print only the reload request: any other
# stdout is shown to the model.
exec 3>&1 >/dev/null 2>&1
# shellcheck disable=SC2034 # line is never read; the loop only drains the input
while read -r line; do :; done

root=/mnt/skills
mode='link'
config=${CLAUDE_CONFIG_DIR-${HOME:-/root}/.claude}
# A relative or empty CLAUDE_CONFIG_DIR gives the CLI a directory relative to
# its own cwd, which no fixed link can point at.
case "$config" in /*) ;; *) exit 0 ;; esac
dir=$config/skills

changed=
set --
for name in file-reading frontend-design pdf-reading product-self-knowledge; do
	src=$root/public/$name
	dst=$dir/$name
	# The first hook links $root/user to where the account's synced skills
	# land. One of this name keeps the name.
	theirs=
	[ -e "$root/user/$name/SKILL.md" ] && theirs=1
	if [ -L "$dst" ] || [ -e "$dst" ]; then
		# Remove only a link whose own text is this hook's target. That
		# needs no read of the catalogue and spares a link to anywhere else.
		if [ "$mode" != link ] || [ -n "$theirs" ]; then
			if [ -L "$dst" ] && [ "$(readlink -- "$dst")" = "$src" ]; then
				rm -f -- "$dst" && changed=1
			fi
		fi
		continue
	fi
	if [ "$mode" = link ] && [ -z "$theirs" ] && [ -e "$src/SKILL.md" ]; then
		set -- "$@" "$src"
	fi
done
if [ $# -gt 0 ]; then
	[ -d "$dir" ] || mkdir -p "$dir" || exit 0
	ln -s -t "$dir" -- "$@"
	for src in "$@"; do
		[ -L "$dir/${src##*/}" ] && changed=1
	done
fi
# Claude Code may list its skills before this script ends, so ask for a reload.
if [ -n "$changed" ]; then
	printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"SessionStart","reloadSkills":true}}' >&3
fi
exit 0
