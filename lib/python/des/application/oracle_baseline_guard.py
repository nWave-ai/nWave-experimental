"""Copied as sitecustomize.py for baseline oracles; never imported by DES.

Keep this startup asset stdlib-only and compatible with Python 3.8.
foreign_roots.json is produced beside the copy by the oracle executor.
"""

try:
    import importlib.machinery
    import importlib.util
    import json
    import os
    import sys

    def _within(path, root):
        try:
            return os.path.commonpath((path, root)) == root
        except ValueError:
            return False

    def _owner(path):
        if not path or path in ("built-in", "frozen"):
            return None
        resolved = os.path.realpath(path)
        if any(_within(resolved, root) for root in _exemptions):
            return None
        return next(
            (root for root in _roots if _within(resolved, root)),
            None,
        )

    def _rebase(path, module):
        owner = _owner(path)
        if owner is None:
            return path
        replacement = os.path.join(
            _tree, os.path.relpath(os.path.realpath(path), owner)
        )
        admitted = (
            replacement
            if os.path.exists(replacement) and _owner(replacement) is None
            else None
        )
        sys.stderr.write(
            "NWAVE-BASELINE-SHADOWED: {} {} -> {}\n".format(
                module, path, admitted or "absent"
            )
        )
        return admitted

    def _paths(paths, module):
        rebased = []
        for entry in paths:
            replacement = _rebase(entry or os.getcwd(), module)
            if replacement is not None:
                rebased.append(
                    entry if _owner(entry or os.getcwd()) is None else replacement
                )
        return rebased

    def _receipt(status, reason=None):
        receipt = {
            "nonce": os.environ["NWAVE_ORACLE_GUARD_NONCE"],
            "status": status,
        }
        if reason is None:
            receipt.update(python=sys.version, executable=sys.executable)
        else:
            receipt["reason"] = reason
        destination = os.path.join(
            os.environ["NWAVE_ORACLE_GUARD_RECEIPTS"],
            f"{os.getpid()}.json",
        )
        temporary = destination + ".tmp"
        with open(temporary, "w") as stream:
            json.dump(receipt, stream)
        os.replace(temporary, destination)  # noqa: PTH105 - keep bootstrap publication on existing os primitives

    def _refuse(reason):
        try:
            _receipt("refused", reason)
        except BaseException:
            pass
        try:
            sys.stderr.write(f"NWAVE-BASELINE-ISOLATION-REFUSED: {reason}\n")
            sys.stderr.flush()
        finally:
            os._exit(3)

    def _cached_modules():
        for name, module in tuple(sys.modules.items()):
            namespace = getattr(module, "__dict__", {})
            locations = [namespace.get("__file__")]
            locations.extend(namespace.get("__path__") or ())
            for location in locations:
                if _owner(location) is not None:
                    raise RuntimeError(
                        f"already-imported module {name} contains foreign source {location}"
                    )

    def _admitted_spec(fullname, spec, path, fallback=True):
        if spec is None:
            return None
        locations = spec.submodule_search_locations
        origin = _rebase(spec.origin, fullname)
        searches = (
            [_rebase(location, fullname) for location in locations]
            if locations is not None
            else None
        )
        changed = origin != spec.origin or (
            searches is not None and searches != list(locations)
        )
        if not changed:
            return spec
        if origin is not None and (searches is None or all(searches)):
            replacement = importlib.util.spec_from_file_location(
                fullname, origin, submodule_search_locations=searches
            )
            if replacement is not None:
                return replacement
        elif spec.origin is None and searches is not None and all(searches):
            replacement = importlib.machinery.ModuleSpec(
                fullname, None, is_package=True
            )
            replacement.submodule_search_locations = searches
            return replacement
        if not fallback:
            return None
        # Editable finders may name a missing foreign file. Let the real path
        # finder recover the baseline module/package from sanitized paths.
        return _admitted_spec(
            fullname,
            importlib.machinery.PathFinder.find_spec(
                fullname, _paths(sys.path if path is None else path, fullname)
            ),
            path,
            fallback=False,
        )

    class _BaselineFinder:
        def __init__(self, finder):
            self.finder = finder

        def __getattr__(self, name):
            return getattr(self.finder, name)

        def find_spec(self, fullname, path=None, target=None):
            try:
                _sanitize_paths()
                path = None if path is None else _paths(path, fullname)
                find_spec = getattr(self.finder, "find_spec", None)
                if find_spec is not None:
                    spec = find_spec(fullname, path, target)
                else:
                    loader = self.finder.find_module(fullname, path)
                    spec = (
                        importlib.util.spec_from_loader(fullname, loader)
                        if loader is not None
                        else None
                    )
                return _admitted_spec(fullname, spec, path)
            except BaseException as error:
                _refuse(f"unsafe lookup for {fullname}: {error}")

    class _BaselinePathFinder(_BaselineFinder):
        def __init__(self, finder, directory):
            super().__init__(finder)
            self.directory = directory

        def find_spec(self, fullname, target=None):
            try:
                _sanitize_paths()
                find_spec = getattr(self.finder, "find_spec", None)
                if find_spec is not None:
                    spec = find_spec(fullname, target)
                else:
                    loader = self.finder.find_module(fullname)
                    spec = (
                        importlib.util.spec_from_loader(fullname, loader)
                        if loader is not None
                        else None
                    )
                return _admitted_spec(fullname, spec, [self.directory], fallback=False)
            except BaseException as error:
                _refuse(f"unsafe path lookup for {fullname}: {error}")

    class _BaselinePathHook:
        def __init__(self, hook):
            self.hook = hook

        def __call__(self, path):
            try:
                rebased = _rebase(path, "sys.path_hooks")
                if rebased is None:
                    raise ImportError("foreign path has no baseline counterpart")
                return _BaselinePathFinder(self.hook(rebased), rebased)
            except ImportError:
                raise
            except BaseException as error:
                _refuse(f"unsafe path hook for {path}: {error}")

    def _wrap_finders():
        sys.meta_path[:] = [
            finder if isinstance(finder, _BaselineFinder) else _BaselineFinder(finder)
            for finder in sys.meta_path
        ]
        sys.path_hooks[:] = [
            hook if isinstance(hook, _BaselinePathHook) else _BaselinePathHook(hook)
            for hook in sys.path_hooks
        ]

    def _sanitize_paths():
        sys.path[:] = _paths(sys.path, "sys.path")
        for entry in tuple(sys.path_importer_cache):
            if _owner(entry) is not None:
                del sys.path_importer_cache[entry]
        # Finders and hooks installed after startup receive the same treatment.
        _wrap_finders()

    def _chain_sitecustomize(guard_dir):
        remaining = [
            entry
            for entry in sys.path
            if os.path.realpath(entry or os.getcwd()) != guard_dir
        ]
        spec = _admitted_spec(
            "sitecustomize",
            importlib.machinery.PathFinder.find_spec("sitecustomize", remaining),
            remaining,
        )
        if spec is None or spec.loader is None:
            return
        module = importlib.util.module_from_spec(spec)
        sys.modules["sitecustomize"] = module
        try:
            spec.loader.exec_module(module)
        except Exception as error:
            # Preserve site's warn-and-continue treatment of an ordinary hook
            # failure, but recheck its resulting imports and paths afterwards.
            if sys.flags.verbose:
                sys.excepthook(type(error), error, error.__traceback__)
            else:
                sys.stderr.write(
                    "Error in sitecustomize; set PYTHONVERBOSE for traceback:\n"
                    f"{type(error).__name__}: {error}\n"
                )

    guard_dir = os.environ["NWAVE_ORACLE_GUARD_DIR"]
    with open(os.path.join(guard_dir, "foreign_roots.json")) as source:
        declared = json.load(source)
    _roots = declared["roots"]
    _exemptions = declared["exemptions"]
    _tree = declared["tree"]
    _cached_modules()
    _sanitize_paths()
    _chain_sitecustomize(os.path.realpath(guard_dir))
    _cached_modules()
    _sanitize_paths()
    _receipt("armed")
except BaseException as startup_error:
    # Include import/bootstrap failures: site.py must not swallow this error
    # and leave the original-source measurement using a contaminated runtime.
    import os
    import sys

    try:
        _receipt("refused", str(startup_error))
    except BaseException:
        pass
    try:
        sys.stderr.write(f"NWAVE-BASELINE-ISOLATION-REFUSED: {startup_error}\n")
        sys.stderr.flush()
    finally:
        os._exit(3)
