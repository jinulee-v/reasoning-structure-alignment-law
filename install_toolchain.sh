#!/bin/bash
# Userspace toolchain for the SARA -> Catala port.  Four environments:
#
#   .toolchain/envs/sara     SWI-Prolog 10.0.0 -- the differential oracle
#   .toolchain/envs/catala   conda-forge OCaml 4.14.2 + opam 2.5
#   .toolchain/opam/catala   opam switch carrying Catala 1.2.1 -- the port
#   .toolchain/envs/cutecat  python, for building Z3 from source
#   .toolchain/opam/cutecat  opam switch carrying CUTECat -- the concolic engine
#
# No root and no system packages: everything lands under the gitignored
# .toolchain/.  Every version is pinned, since the port is validated against
# exactly these -- see `## Toolchain notes` in README.md.
#
# Takes about two hours: an hour per switch for opam to build OCaml 4.14.2 from
# source, plus twenty minutes of Z3.
#
# The switch prefix is compiled into the `catala` and `clerk` binaries, so a
# switch built here belongs here: moving `.toolchain/` afterwards needs the
# OCAMLLIB/OCAMLPATH/CAML_LD_LIBRARY_PATH overrides that
# `saralib.paths.catala_env` sets, or another run of this script.
#
# ---- stages --------------------------------------------------------------
# Each expensive step is a named stage; the argument is a comma-separated list
# of the stages to run (default: all):
#
#   bash install_toolchain.sh              # everything
#   bash install_toolchain.sh cutecat      # just CUTECat
#   bash install_toolchain.sh swipl,ocaml  # just those two
#
# Stages: swipl, ocaml, catala, cutecat.  Everything outside a stage (the
# micromamba download, `opam init`, the variables, the final checks) is cheap
# and idempotent, and always runs.
set -u

# The script lives at the repository root, so its own directory is $R.
R="$(cd "$(dirname "$0")" && pwd)"
T="$R/.toolchain"
MM="$T/bin/micromamba"
# Kept before anything is prepended to PATH: the Z3 build below needs a PATH
# with no conda environment on the front of it.  See the note there.
SYSTEM_PATH="$PATH"
export MAMBA_ROOT_PREFIX="$T/mamba"

SWIPL_VERSION=10.0.0
OCAML_VERSION=4.14.2
CATALA_VERSION=1.2.1

# CUTECat is not released: it is the `cutecat-rebase` branch of the Catala
# compiler, whose `compiler/concolic/` adds a `catala concolic` subcommand.
# Pinned to a commit rather than the branch, because the branch is rebased.
CUTECAT_REPO=https://github.com/CatalaLang/catala.git
CUTECAT_BRANCH=cutecat-rebase
CUTECAT_COMMIT=e9e8628ef3a2f5fb7a3d7d048a0c66c6e8733013
CUTECAT_PATCH="$R/cutecat_scripts/patches/unused-option-sort.patch"
CUTECAT_COVERAGE_PATCH="$R/cutecat_scripts/patches/coverage-with-input.patch"
CUTECAT_EPOS_PATCH="$R/cutecat_scripts/patches/epos-is-a-value.patch"
CUTECAT_TOINT_PATCH="$R/cutecat_scripts/patches/toint-rat.patch"
CUTECAT_LISTS_PATCH="$R/cutecat_scripts/patches/concolic-lists.patch"
CUTECAT_LIST_STDLIB_PATCH="$R/cutecat_scripts/patches/concolic-list-stdlib.patch"
CUTECAT_NESTED_LISTS_PATCH="$R/cutecat_scripts/patches/concolic-nested-lists.patch"
CUTECAT_CONCOLIC_COVERAGE_PATCH="$R/cutecat_scripts/patches/concolic-coverage.patch"
CUTECAT_OPTIONS_PATCH="$R/cutecat_scripts/patches/concolic-options.patch"
CUTECAT_REPRESENTATION_FIXES_PATCH="$R/cutecat_scripts/patches/concolic-representation-fixes.patch"
CUTECAT_UNICODE_IDENTIFIERS_PATCH="$R/cutecat_scripts/patches/unicode-identifiers.patch"
Z3_VERSION=4.13.3

STAGES="${1:-all}"
want() {
    case ",$STAGES," in
        *",all,"* | *",$1,"*) return 0 ;;
        *) return 1 ;;
    esac
}

log() { printf '\n=== %s ===\n' "$*"; }
skip() { printf '\n--- skipping %s (not in "%s") ---\n' "$*" "$STAGES"; }
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
if want swipl; then
    log "SWI-Prolog $SWIPL_VERSION"
    "$MM" create -y -p "$T/envs/sara" -c conda-forge \
        "swi-prolog=$SWIPL_VERSION" || die "swipl env"
else
    skip "SWI-Prolog"
fi

# ---- OCaml + opam --------------------------------------------------------
# gmp and pkg-config are here because conf-gmp builds against them and there is
# no system gmp; git/unzip/rsync/make/m4 are opam's own build dependencies;
# ninja because clerk shells out to it and catala depends on conf-ninja.
# ninja is taken from conda-forge deliberately: the first build of this tree
# satisfied conf-ninja from `~/.pyenv/shims/ninja`, a binary outside the tree,
# so the toolchain only looked self-contained.
ENV="$T/envs/catala"
if want ocaml; then
    log "OCaml $OCAML_VERSION + opam"
    PKGS=("ocaml=$OCAML_VERSION" opam gmp pkg-config make m4 unzip rsync git ninja)
    if [ -d "$ENV/conda-meta" ]; then
        "$MM" install -y -p "$ENV" -c conda-forge "${PKGS[@]}" || die "catala env"
    else
        "$MM" create -y -p "$ENV" -c conda-forge "${PKGS[@]}" || die "catala env"
    fi
else
    skip "OCaml + opam"
fi

export PATH="$ENV/bin:$PATH"
export CPATH="$ENV/include:${CPATH:-}"
export LIBRARY_PATH="$ENV/lib:${LIBRARY_PATH:-}"
export LD_LIBRARY_PATH="$ENV/lib:${LD_LIBRARY_PATH:-}"
export PKG_CONFIG_PATH="$ENV/lib/pkgconfig:${PKG_CONFIG_PATH:-}"
export OPAMROOT="$T/opam"
export OPAMYES=1
# opam's default is 1 job, which is an hour of OCaml and twenty minutes of Z3
# spent on one core.  Capped rather than `nproc` because this runs on a shared
# login node.
export OPAMJOBS="${OPAMJOBS:-$(( $(nproc) < 16 ? $(nproc) : 16 ))}"

log "opam root"
opam init --bare --disable-sandboxing --no-setup || die "opam init"
# opam resolves "external dependencies" through the OS package manager, so
# conf-ninja makes it want `apt-get install ninja-build` and abort without root.
# ninja and gmp came from conda-forge above and are on PATH, so depext is off.
opam option --global depext=false || die "opam option depext"

# `ocaml-system` would adopt the conda compiler and save the hour, but its
# configuration does not satisfy every catala dependency, so it is only tried
# first and a switch otherwise builds 4.14.2 itself.  That is nearly the whole
# runtime, so an existing switch is reused.
make_switch() {
    if opam switch list --short 2>/dev/null | grep -qx "$1"; then
        echo "switch '$1' already exists; reusing it"
    else
        opam switch create "$1" ocaml-system \
            || opam switch create "$1" "$OCAML_VERSION" \
            || die "opam switch $1"
    fi
}

# ---- Catala --------------------------------------------------------------
if want catala; then
    log "opam switch 'catala'"
    make_switch catala
    eval "$(opam env --switch=catala --set-switch)"
    opam update || die "opam update"

    log "Catala $CATALA_VERSION"
    opam install -y "catala.$CATALA_VERSION" || die "catala"
else
    skip "Catala"
fi

# ---- CUTECat -------------------------------------------------------------
# CUTECat (see `doc/concolic/README.md` in the branch) is a second Catala
# compiler: same 1.2 series plus `compiler/concolic/`, which walks a scope's
# paths under Z3 and prints one input/output pair per path.  It gets its own
# switch, since installing it into `catala` would replace the pinned 1.2.1 both
# ports are validated against.
if want cutecat; then
    # Z3's build driver is `python3 scripts/mk_make.py`, and the python3 on this
    # machine's PATH is a pyenv shim, so the build gets a conda-forge one.  The
    # C++ compiler stays a system dependency, as the C compiler already is.
    log "python (for the Z3 build)"
    PYENV="$T/envs/cutecat"
    if [ -d "$PYENV/conda-meta" ]; then
        "$MM" install -y -p "$PYENV" -c conda-forge python || die "cutecat python env"
    else
        "$MM" create -y -p "$PYENV" -c conda-forge python || die "cutecat python env"
    fi
    command -v c++ >/dev/null || die "no C++ compiler on PATH (Z3 needs one)"

    log "CUTECat source @ ${CUTECAT_COMMIT:0:12}"
    SRC="$T/src/catala-cutecat"
    if [ ! -d "$SRC/.git" ]; then
        mkdir -p "$T/src"
        git clone --branch "$CUTECAT_BRANCH" "$CUTECAT_REPO" "$SRC" \
            || die "cutecat clone"
    fi
    git -C "$SRC" fetch origin "$CUTECAT_BRANCH" || die "cutecat fetch"
    git -C "$SRC" checkout --detach "$CUTECAT_COMMIT" || die "cutecat checkout"
    # A checkout of the already-selected detached commit leaves modifications
    # in place. This stage is a reproducible rebuild from the pinned source;
    # restore tracked files before applying the repository-owned patch stack.
    git -C "$SRC" reset --hard "$CUTECAT_COMMIT" || die "cutecat reset"
    git -C "$SRC" clean -xdf >/dev/null || die "cutecat clean"
    # The SARA world model has option-bearing declarations the scalar scopes
    # never read, and upstream aborts merely creating their sorts.  Give such
    # fields the opaque treatment unsupported arrays get; an option actually
    # evaluated is still rejected by the default/value conversion code.
    if git -C "$SRC" apply --reverse --check "$CUTECAT_PATCH" 2>/dev/null; then
        echo "CUTECat option compatibility patch already applied"
    else
        git -C "$SRC" apply --check "$CUTECAT_PATCH" \
            && git -C "$SRC" apply "$CUTECAT_PATCH" \
            || die "cutecat option compatibility patch"
    fi
    if git -C "$SRC" apply --reverse --check "$CUTECAT_COVERAGE_PATCH" 2>/dev/null; then
        echo "CUTECat coverage-input patch already applied"
    else
        git -C "$SRC" apply --check "$CUTECAT_COVERAGE_PATCH" \
            && git -C "$SRC" apply "$CUTECAT_COVERAGE_PATCH" \
            || die "cutecat coverage-input patch"
    fi
    # Two features the concolic interpreter leaves as `failwith`, both reached
    # by ordinary rules in the ports.
    #
    # `EPos` is a reified source position, passed through untouched by the plain
    # interpreter so a failing date operation can say where it failed.  Aborting
    # on it makes every date rule unreachable, `Date.of_year_month_day` carrying
    # one.
    #
    # `ToInt_rat` is decimal-to-integer conversion, how a phase-out counts whole
    # steps.  It means `Q.to_bigint`, truncation towards zero, while Z3's
    # `mk_real2int` is floor, so the patch reflects negatives through zero: with
    # floor the solver can return an input whose re-execution takes another path.
    for _p in "$CUTECAT_EPOS_PATCH" "$CUTECAT_TOINT_PATCH" \
              "$CUTECAT_LISTS_PATCH" "$CUTECAT_LIST_STDLIB_PATCH" \
              "$CUTECAT_NESTED_LISTS_PATCH" \
              "$CUTECAT_CONCOLIC_COVERAGE_PATCH" \
              "$CUTECAT_OPTIONS_PATCH" \
              "$CUTECAT_REPRESENTATION_FIXES_PATCH" \
              "$CUTECAT_UNICODE_IDENTIFIERS_PATCH"; do
        if git -C "$SRC" apply --reverse --check "$_p" 2>/dev/null; then
            echo "CUTECat patch already applied: $(basename "$_p")"
        else
            git -C "$SRC" apply --check "$_p" \
                && git -C "$SRC" apply "$_p" \
                || die "cutecat patch $(basename "$_p")"
        fi
    done

    log "opam switch 'cutecat'"
    make_switch cutecat
    eval "$(opam env --switch=cutecat --set-switch)"
    opam update || die "opam update"

    # z3 is in catala-proof.opam rather than catala.opam, so `--deps-only` below
    # will not pull it and it goes in by hand first.  The opam package builds Z3,
    # C++ and OCaml bindings together, which is the twenty minutes.
    #
    # Z3 is built by the system C++ compiler, so the conda environments have to
    # be out of its way: `envs/catala/bin` carries conda's binutils, and a
    # /usr/bin `g++` that finds conda's `ld` links against conda's sysroot glibc,
    # failing with `libdl.so.2: undefined reference to _dl_vsym@GLIBC_PRIVATE`,
    # which z3's build script reports as "C++ compiler was not found".  CPATH and
    # LIBRARY_PATH would mix in the same environment's headers and libraries.  So
    # the Z3 build and the later Catala link put the system PATH in front, keep
    # only the switch (for ocamlfind) and the python environment ahead of it, and
    # drop the three include/library variables.  `envs/cutecat/bin` is safe
    # there: it carries no plain `ld`.
    log "Z3 $Z3_VERSION"
    env -u CPATH -u LIBRARY_PATH -u LD_LIBRARY_PATH \
        PATH="$OPAMROOT/cutecat/bin:$PYENV/bin:$SYSTEM_PATH:$ENV/bin" \
        "$ENV/bin/opam" install -y "z3.$Z3_VERSION" || die "z3"

    log "CUTECat"
    opam install -y --deps-only "$SRC/catala.opam" || die "cutecat deps"
    # Pinned to the checkout rather than installed from it, so that a later
    # `opam reinstall catala` in this switch rebuilds *this* source and not the
    # released 1.2.1.  This needs the same system linker used to build Z3:
    # otherwise OCaml finds conda's older-sysroot `ld` and cannot link libz3.
    opam pin add -y --no-action --kind=path catala "$SRC" \
        || die "cutecat pin"
    env -u CPATH -u LIBRARY_PATH -u LD_LIBRARY_PATH \
        PATH="$OPAMROOT/cutecat/bin:$PYENV/bin:$SYSTEM_PATH:$ENV/bin" \
        "$ENV/bin/opam" install -y catala \
        || die "cutecat install"
else
    skip "CUTECat"
fi

# ---- verify --------------------------------------------------------------
log "versions"
"$T/envs/sara/bin/swipl" --version || die "swipl not runnable"
eval "$(opam env --switch=catala --set-switch)"
catala --version || die "catala not runnable"
clerk --version || die "clerk not runnable"
if [ -x "$OPAMROOT/cutecat/bin/catala" ]; then
    echo -n "cutecat: "
    "$OPAMROOT/cutecat/bin/catala" --version || die "cutecat catala not runnable"
    "$OPAMROOT/cutecat/bin/catala" concolic --help=plain >/dev/null \
        || die "cutecat catala has no 'concolic' subcommand"
    echo "ok: 'catala concolic' is available"
fi

log "self-containment"
# The switch prefix is compiled into these two binaries, so either naming a
# sibling of this tree means the switch was built elsewhere and relocated, which
# works only through `catala_env`'s overrides.  A fresh build names only $R.
P="$(dirname "$R")"
for f in "$OPAMROOT/catala/bin/catala" "$OPAMROOT/catala/bin/clerk" \
         "$OPAMROOT/cutecat/bin/catala"; do
    [ -x "$f" ] || continue
    stray=$(strings -a "$f" 2>/dev/null | grep -F "$P/" | grep -vF "$R/" | sort -u)
    if [ -n "$stray" ]; then
        echo "WARNING: $f names paths outside this tree:"
        echo "$stray" | sed 's/^/    /'
    else
        echo "ok: $f names no directory but $R"
    fi
done

echo
echo "toolchain ready under $T"
