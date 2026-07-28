"""Error hierarchy for telemetry_mining."""


class TelemetryMiningError(Exception):
    """Base class for all telemetry_mining errors."""


class MissingDependencyError(TelemetryMiningError):
    """A required compiled dependency (psycopg2, fitsio, ...) is unusable.

    This account's default conda environment does not have a working
    psycopg2/numpy build. Point the user at a known-good interpreter rather
    than letting them chase an opaque ImportError.
    """

    def __init__(self, module_name: str, original_error: Exception):
        message = (
            f"Failed to import '{module_name}': {original_error}\n"
            "This usually means the current Python environment is missing a working "
            "compiled build of this package. Try running with:\n"
            "  /global/common/software/desi/perlmutter/desiconda/20260227-2.3.1/conda/bin/python3\n"
            "or activate the DESI environment first:\n"
            "  source /global/common/software/desi/desi_environment.sh master"
        )
        super().__init__(message)
        self.module_name = module_name
        self.original_error = original_error

    def __reduce__(self):
        # Default Exception pickling replays __init__(*self.args), but self.args
        # is just (message,) from super().__init__() above -- not the real
        # (module_name, original_error) this constructor needs. Without this,
        # unpickling (e.g. an error crossing a ProcessPoolExecutor boundary)
        # raises a fresh, confusing TypeError instead of the original error.
        return (self.__class__, (self.module_name, self.original_error))


class ExposureNotFoundError(TelemetryMiningError):
    """Raised when an exposure cannot be located on disk or in the database."""

    def __init__(self, expid: int, detail: str):
        super().__init__(f"Exposure {expid} not found: {detail}")
        self.expid = expid
        self.detail = detail

    def __reduce__(self):
        return (self.__class__, (self.expid, self.detail))


class DatabaseUnavailableError(TelemetryMiningError):
    """Wraps a psycopg2 connection/operational failure with actionable context."""

    def __init__(self, original_error: Exception):
        message = (
            f"Could not connect to the DESI replicator database: {original_error}\n"
            "Check that DOS_DB_HOST/DOS_DB_PORT/DOS_DB_NAME/DOS_DB_READER/"
            "DOS_DB_READER_PASSWORD are set and that the host is reachable "
            "(e.g. VPN/network access to lbl.gov)."
        )
        super().__init__(message)
        self.original_error = original_error

    def __reduce__(self):
        return (self.__class__, (self.original_error,))


class DataSourceUnavailableError(TelemetryMiningError):
    """A data source isn't configured for this site at all -- not a missing record.

    Distinct from ExposureNotFoundError (a specific exposure/row is missing)
    and DatabaseUnavailableError (a DB connection failed): this means the
    current Config simply has no such source for this site (e.g. KPNO has no
    offline/redux reduction pipeline), so no I/O is attempted at all.
    """
