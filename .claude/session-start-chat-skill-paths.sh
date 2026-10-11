#!/bin/sh
# SessionStart hook for a Cowork Remote session that began as a claude.ai chat.
# The chat told the model its skills live under /mnt/skills/user, /organization,
# /private and /plugins; link those to the directory Claude Code syncs skills
# into, <config dir>/skills/synced/<org uuid>_<account uuid or "unbound">.

# Claude Code waits for this script before it reads the session's first
# message, and each program the script starts adds to that wait. So when
# /mnt/skills exists and both uuids are lower case, start no program but ln.

# Drain the hook's JSON input; print nothing, because SessionStart stdout is
# shown to the model; and exit 0 whatever fails, so a missing link never costs
# the session.
exec >/dev/null 2>&1
# shellcheck disable=SC2034 # line is never read; the loop only drains the input
while read -r line; do :; done

root=/mnt/skills
h='[0123456789abcdef]'
h4=$h$h$h$h
uuid=$h4$h4-$h4-$h4-$h4-$h4$h4$h4
# to_uuid sets id to $1 with surrounding whitespace trimmed and A-F made lower
# case, fails unless id is then a uuid, and exits if tr fails. Under dash,
# only ASCII whitespace is trimmed.
to_uuid() {
	id=$1
	while :; do
		case $id in
		[[:space:]]*) id=${id#?} ;;
		*[[:space:]]) id=${id%?} ;;
		*) break ;;
		esac
	done
	case $id in *[ABCDEF]*) id=$(printf '%s' "$id" | tr ABCDEF abcdef) || exit 0 ;; *) ;; esac
	# shellcheck disable=SC2254 # $uuid is a pattern, not a literal
	case $id in $uuid) return 0 ;; *) return 1 ;; esac
}

to_uuid "${CLAUDE_CODE_ORGANIZATION_UUID:-}" || exit 0
org=$id
if to_uuid "${CLAUDE_CODE_ACCOUNT_UUID:-}"; then account=$id; else account=unbound; fi
config=${CLAUDE_CONFIG_DIR-${HOME:-/root}/.claude}
# A relative or empty CLAUDE_CONFIG_DIR gives the CLI a directory relative to
# its own cwd, which no fixed link can point at.
case "$config" in /*) ;; *) exit 0 ;; esac
bucket="$config/skills/synced/${org}_${account}"

[ -d "$root" ] || mkdir -p "$root" || exit 0
for dir in user organization private plugins; do
	# Once $bucket exists, a link that leads to it is kept. ln replaces any other
	# link and fails, changing nothing, where a real directory already exists.
	# shellcheck disable=SC3013 # dash and bash have -ef; a shell without it runs ln
	[ "$root/$dir" -ef "$bucket" ] || ln -sfnT -- "$bucket" "$root/$dir"
done
exit 0
