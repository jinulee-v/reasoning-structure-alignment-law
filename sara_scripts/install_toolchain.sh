#!/bin/bash
# Userspace toolchain for the SARA -> Catala port.  Two environments:
#
#   .toolchain/envs/sara     SWI-Prolog 10.0.0 -- the differential oracle
#   .toolchain/envs/catala   conda-forge OCaml 4.14.2 + opam 2.5
#   .toolchain/opam/catala   opam switch carrying Catala 1.2.1 -- the port
#
# No root and no system packages: everything lands under .toolchain/, which is
# gitignored.  Every version here is pinned, because the port is validated
# against exactly these two -- see `## Toolchain notes` in README.md.
#
# Takes about an hour, nearly all of it opam building OCaml 4.14.2 from source.
#
# The switch prefix is compiled into the `catala` and `clerk` binaries, so a
# switch built here belongs here: moving `.toolchain/` afterwards needs the
# OCAMLLIB/OCAMLPATH/CAML_LD_LIBRARY_PATH overrides that
# `saralib.paths.catala_env` sets, or another run of this script.
set -u

R="$(cd "$(dirname "$0")/.." && pwd)"
T="$R/.toolchain"
MM="$T/bin/micromamba"
export MAMBA_ROOT_PREFIX="$T/mamba"

SWIPL_VERSION=10.0.0
OCAML_VERSION=4.14.2
CATALA_VERSION=1.2.1

log() { printf '\n=== %s ===\n' "$*"; }
die() { printf '\nFAILED: %s\n' "$*" >&2; exit 1; }

# ---- micromamba ----------------------------------------------------------
if [ ! -x "$MM" ]; then
    log "fetching micromamba"
    mkdir -p "$T/bin"
    curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest \
        | tar -xj -C "$T" bin/micromamba || die "micromamba download"
fi

# ---- SWI-Prolog: the oracle ----------------------------------------------
# SARA pins 7.2.3 (2015), which conda-forge does not carry; 10.0.0 differs only
# in D1 of DEVIATIONS.md (`rdiv/2` rejects floats), which the port's copy of the
# statutes patches around.
log "SWI-Prolog $SWIPL_VERSION"
"$MM" create -y -p "$T/envs/sara" -c conda-forge \
    "swi-prolog=$SWIPL_VERSION" || die "swipl env"

# ---- OCaml + opam --------------------------------------------------------
# gmp and pkg-config are here because conf-gmp builds against them and there is
# no system gmp; git/unzip/rsync/make/m4 are opam's own build dependencies;
# ninja because clerk shells out to it and catala depends on conf-ninja.
#
# ninja is the one that has to be said out loud.  The first build of this tree
# satisfied conf-ninja from `~/.pyenv/shims/ninja` --- a binary outside the
# tree, on the machine by accident --- so the toolchain only looked
# self-contained. Taking it from conda-forge is what makes it actually so.
log "OCaml $OCAML_VERSION + opam"
ENV="$T/envs/catala"
PKGS=("ocaml=$OCAML_VERSION" opam gmp pkg-config make m4 unzip rsync git ninja)
if [ -d "$ENV/conda-meta" ]; then
    "$MM" install -y -p "$ENV" -c conda-forge "${PKGS[@]}" || die "catala env"
else
    "$MM" create -y -p "$ENV" -c conda-forge "${PKGS[@]}" || die "catala env"
fi

export PATH="$ENV/bin:$PATH"
export CPATH="$ENV/include:${CPATH:-}"
export LIBRARY_PATH="$ENV/lib:${LIBRARY_PATH:-}"
export LD_LIBRARY_PATH="$ENV/lib:${LD_LIBRARY_PATH:-}"
export PKG_CONFIG_PATH="$ENV/lib/pkgconfig:${PKG_CONFIG_PATH:-}"
export OPAMROOT="$T/opam"
export OPAMYES=1

# ---- Catala --------------------------------------------------------------
log "opam switch"
opam init --bare --disable-sandboxing --no-setup || die "opam init"
# opam resolves "external dependencies" through the OS package manager, so
# conf-ninja makes it want `apt-get install ninja-build` and abort without
# root.  Nothing here is a system package: ninja came from conda-forge above
# and gmp with it, both on PATH.  Turning depext off is what lets opam use
# them instead of insisting on apt.
opam option --global depext=false || die "opam option depext"
# `ocaml-system` would adopt the conda compiler and save the hour, but its
# configuration does not satisfy every catala dependency here, so the switch
# builds 4.14.2 itself and `ocaml-system` is only tried first.  Building the
# compiler is nearly the whole runtime of this script, so an existing switch is
# reused --- rerunning after a failed `opam install` costs minutes, not an hour.
if opam switch list --short 2>/dev/null | grep -qx catala; then
    echo "switch 'catala' already exists; reusing it"
else
    opam switch create catala ocaml-system \
        || opam switch create catala "$OCAML_VERSION" \
        || die "opam switch"
fi
eval "$(opam env --switch=catala --set-switch)"
opam update || die "opam update"

log "Catala $CATALA_VERSION"
opam install -y "catala.$CATALA_VERSION" || die "catala"

# ---- verify --------------------------------------------------------------
log "versions"
"$T/envs/sara/bin/swipl" --version || die "swipl not runnable"
catala --version || die "catala not runnable"
clerk --version || die "clerk not runnable"

log "self-containment"
# The switch prefix is compiled into these two binaries, so if either names a
# sibling of this tree the switch was built elsewhere and merely relocated ---
# which works, but only through `catala_env`'s overrides.  A fresh build here
# should name nothing but $R.
P="$(dirname "$R")"
for f in "$OPAMROOT/catala/bin/catala" "$OPAMROOT/catala/bin/clerk"; do
    stray=$(strings -a "$f" 2>/dev/null | grep -F "$P/" | grep -vF "$R/" | sort -u)
    if [ -n "$stray" ]; then
        echo "WARNING: $(basename "$f") names paths outside this tree:"
        echo "$stray" | sed 's/^/    /'
    else
        echo "ok: $(basename "$f") names no directory but $R"
    fi
done

echo
echo "toolchain ready under $T"
