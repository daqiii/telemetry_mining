# Field / Column Glossary

A reference for every FITS header, CSV column, and database column this
project actually touches — what it means (where known) and a real example
value. Companion to `API.md` (which documents the Python API); this
document is about the underlying **data**, independent of any code.

## Scope

This is **not** an exhaustive dump of everything that exists in DESI's data
systems — in particular, the `telemetry` database schema alone has 93
tables (thousands of columns), and only the ones `telemetry_mining` actually
queries are listed here. What's covered:

- Every file in a raw exposure directory that this project reads (FITS
  headers, coordinates, ETC JSON, centroids JSON, `fiberassign-<tileid>.fits.gz`).
- Every offline QA/reduction source integrated so far (`exposures-daily.csv`,
  `exposure_table_<night>.csv`, `tiles-daily.csv`, cframe `FIBERMAP`/`SCORES`,
  the GFA offline summary, `exposure-qa-<expid>.fits`, `calibstars-<expid>.csv`).
- The `exposure` schema in full (`exposure.exposure`'s 187 columns, plus
  `stars`/`comments`/`positions`/`headers`).
- The specific `telemetry` schema tables this project queries so far
  (`guider_centroids`, `environmentmonitor_telescope`, `environmentmonitor_tower`,
  `environmentmonitor_dust`).

**To explore a `telemetry` table not listed here**, list its columns with
`telemetry_mining.db.fetch_all`. The full working call (swap in `<your table>`):
```python
from telemetry_mining import Config, db

cols = db.fetch_all(
    Config.default(),                                    # 1st arg is ALWAYS a Config
    "SELECT column_name, data_type FROM information_schema.columns "
    "WHERE table_schema='telemetry' AND table_name='<your table>'",
)
for c in cols:                     # each row behaves like a dict
    print(c["column_name"], c["data_type"])
```
`fetch_all` returns a `list` of row-dicts. Change `table_schema='telemetry'` to
`'exposure'` or `'alarms'` to inspect those schemas instead. To pull actual data
(not just the column list), `db.fetch_df(Config.default(), "SELECT * FROM
telemetry.<your table> LIMIT 5")` returns a pandas `DataFrame`. See `API.md`'s
"Direct database access" section for the full `fetch_all`/`fetch_one`/`fetch_df`
signatures.

Many common telemetry tables are **already listed** (columns, types, and a
sampled value) in the [**Appendix: additional telemetry tables**](#appendix-additional-telemetry-tables)
at the end of this file — check there before querying `information_schema` yourself.

Every description below reflects what's been *verified* (against the
installed pipeline source, or by direct comparison against another source
for the same real exposure) or is left blank rather than guessed.

## How this was generated

Programmatically, against one real, recent reference exposure
(**expid 359483, night 20260702** — chosen because it has data in every
source covered here: cframes, `exposure-qa`, GFA summary, redux, DB record),
not hand-typed — so example values and column lists are exactly what's on
disk/in the DB as of 2026-07-16, not transcribed from memory. Descriptions
come from a hand-maintained mapping built from this project's development,
merged with the official comments in `~/fitsheader.py` (supplied 2026-07-16
— these apparently don't make it into the real FITS files, for reasons
unknown) for the main exposure header specifically: 429 of that header's 440
keys have a description as a result. Anything still without one is left
blank on purpose rather than guessed.

This means: **if the underlying datamodel changes** (columns added/removed/
renamed — confirmed to happen; the DESI data-systems team's own tooling
handles this with explicit missing-key tracking when reading FITS headers),
this document can go stale. Re-running the generator script
(`scripts/build_fields_glossary.py`) against a newer exposure is the
fastest way to refresh it.

## The `Source` column

Every table below has a `Source` column: how to actually fetch that field
through `telemetry_mining`, using the `resolve_spec` dotted-path mini-language
(`telemetry_mining.query`, e.g. `db_row['tcs']['mount_ha']`) or a short accessor
call (e.g. `exp.telemetry('environmentmonitor_telescope', columns=['air_temp'])`)
where the field is directly reachable that way.

A **`—`** means the field isn't surfaced individually. Rather than repeat the
same explanation on every such row, the route to it — a direct
`telemetry_mining.db.fetch_df` query, a lower-level function like
`redux.exposure_table_row(...)`, or a custom `TableSource` — is stated **once**
in that section's intro note (the paragraph under the `##` heading). This is why,
for example, tile-level tables indexed by `TILEID` and the un-accessored
`exposure.positions`/`exposure.headers` show a column of `—`: read the section
note, not each row.

**Field names don't always match verbatim across sources for the same
underlying quantity** — this glossary's names come mostly from
`fitsheader.py`'s FITS-header notation, which isn't necessarily how the same
value is spelled in a DB jsonb blob. The clearest real example: the FITS
header's rotator-rate keyword is `ROTRATE` (all caps, no underscore), while
the same physical quantity in the DB's `hexapod` jsonb block is keyed
`rot_rate` (lowercase, underscore) — and the `exposure.exposure` table also
has a flat top-level `rotrate` column that looks like a third candidate but is
actually dead (see that row below). Don't assume a name-based lookup would
work across sources without checking each `Source` cell individually; that's
exactly why this column exists instead of one.

---

## Exposure directory: `desi-<expid>.fits.fz` header (`SPEC` extension)

Live example: expid 359483, night 20260702. 440 keys total; most descriptions below come from `fitsheader.py` (official comments the user supplied -- 429/440 keys here have one -- these don't actually appear in the real FITS files, for reasons unknown). A handful with project-specific notes (e.g. cross-checked against another source) were written by hand and take priority over that file.

| Field | Type | Description | Example value | Source |
|---|---|---|---|---|
| ACQCAM | str | Acquisition cameras used for this exposure | GUIDE0,GUIDE2,GUIDE3,GUIDE5,GUIDE7,GUIDE8 | `header.ACQCAM` |
| ACQFWHM | float | [arcsec] FWHM of guide star PSF in acq. image | 2.279347 | `header.ACQFWHM` |
| ACQTIME | float | [s] acqusition image exposure time | 15.0 | `header.ACQTIME` |
| ACTTEFF | float | [s] Actual effective exposure time | 182.517883 | `header.ACTTEFF` |
| ADC1HOME | bool | ADC 1 at home position if True | False | `header.ADC1HOME` |
| ADC1NREV | float | ADC 1 number of revs | 0.0 | `header.ADC1NREV` |
| ADC1PHI | float | [deg] ADC 1 angle | 348.680004 | `header.ADC1PHI` |
| ADC1STAT | str | ADC 1 status | STOPPED | `header.ADC1STAT` |
| ADC2HOME | bool | ADC 2 at home position if True | False | `header.ADC2HOME` |
| ADC2NREV | float | ADC 2 number of revs | 0.0 | `header.ADC2NREV` |
| ADC2PHI | float | [deg] ADC 2 angle | 54.260002 | `header.ADC2PHI` |
| ADC2STAT | str | ADC 2 status | STOPPED | `header.ADC2STAT` |
| ADCCORR | bool | Correct pointing for ADC setting if True | True | `header.ADCCORR` |
| AIRMASS | float | Airmass at exposure | 1.382467 | `header.AIRMASS` |
| ALARM | bool | UPS major alarm or check battery | False | `header.ALARM` |
| ALARM-ON | bool | UPS active alarm condition | False | not expressible as `header.ALARM-ON` -- hyphen breaks resolve_spec's identifier syntax; use a callable, e.g. `lambda exp: exp.header['ALARM-ON']` |
| AMBIENTS | float | [deg C] ambient temperature south | 19.6 | `header.AMBIENTS` |
| AMNIENTN | float | [deg C] ambient temperature north | 18.3 | `header.AMNIENTN` |
| ASTRFWHM | float | [arcsec] GFAPROC astrometry fwhm | 2.3 | `header.ASTRFWHM` |
| ASTRGFAS | int | GFAPROC GFAs in astrometry solution | 6 | `header.ASTRGFAS` |
| ASTRMATC | int | GFAPROC matched stars | 35 | `header.ASTRMATC` |
| ASTRMETR | bool | GFAPROC astrometry available | True | `header.ASTRMETR` |
| ASTRMOFF | float | GFAPROC astrometry mag offset | 0.14 | `header.ASTRMOFF` |
| ASTRRMSX | float | [arcsec] GFAPROC astrometry rms x | 0.055 | `header.ASTRRMSX` |
| ASTRRMSY | float | [arcsec] GFAPROC astrometry rms y | 0.081 | `header.ASTRRMSY` |
| ASTRSTAR | bool | GFAPROC found stars | True | `header.ASTRSTAR` |
| BACKLIT | str | Fibers are backlit if True | off | `header.BACKLIT` |
| BATTERY | float | [%] UPS Battery left | 100.0 | `header.BATTERY` |
| BEYONDP | bool | Telescope is beyond pole | False | `header.BEYONDP` |
| BITPIX | int | Bits per pixel/data value | 8 | `header.BITPIX` |
| BSCALE | int | Scale factor for scaled data | 1 | `header.BSCALE` |
| BZERO | int | Zero-point offset for scaled data | 32768 | `header.BZERO` |
| CAMSHUT | str | Shutter status during observation | open | `header.CAMSHUT` |
| CCDSPECS | str | Participating ccd spectrographs | SP0,SP1,SP2,SP3,SP4,SP5,SP6,SP7,SP8,SP9 | `header.CCDSPECS` |
| CFLOOR | float | [deg C] temperature on C floor | 19.8 | `header.CFLOOR` |
| CHECKSUM | str | FITS file checksum | Q6lWQ3jTQ3jTQ3jT | `header.CHECKSUM` |
| CLOSSHUT | float | [s] Time it takes exposure shutter to close | 0.591 | `header.CLOSSHUT` |
| COMPAMB | float | [deg C] Computer room ambient temperature | 19.2 | `header.COMPAMB` |
| COMPDEW | float | [deg C] Computer room dewpoint | -2.9 | `header.COMPDEW` |
| COMPHUM | float | [%] Computer room humidity | 16.5 | `header.COMPHUM` |
| COMPTEMP | float | [deg C] Computer room hygrometer temperature | 24.1 | `header.COMPTEMP` |
| CONSTVER | str | Constants version | DESI:CURRENT | `header.CONSTVER` |
| CONVERGD | bool | Positioning loop converged (CNFRC>0.95) | False | `header.CONVERGD` |
| CORRCTOR | str | Corrector Identification | DESI Corrector | `header.CORRCTOR` |
| COSMSPLT | bool | Cosmics split exposure if true | False | `header.COSMSPLT` |
| DATASUM | str | Checksum of the data unit only | 306780459 | `header.DATASUM` |
| DATE-OBS | str | Shutter-open timestamp, ISO 8601 (fractional seconds can exceed 6 digits) | 2026-07-03T04:09:45.563203328 | not expressible as `header.DATE-OBS` -- hyphen breaks resolve_spec's identifier syntax; use a callable, e.g. `lambda exp: exp.header['DATE-OBS']` |
| DEWPOINT | float | [deg C] (outside) dewpoint | -12.2 | `header.DEWPOINT` |
| DOMEAZ | float | [deg] Dome azimuth angle | 208.448 | `header.DOMEAZ` |
| DOMEBLOW | float | [deg C] temperature at dome back, lower | 21.3 | `header.DOMEBLOW` |
| DOMEBUP | float | [deg C] temperature at dome back, upper | 21.9 | `header.DOMEBUP` |
| DOMELLOW | float | [deg C] temperature at dome left, lower | 20.4 | `header.DOMELLOW` |
| DOMELUP | float | [deg C] temperature at dome left, upper | 20.8 | `header.DOMELUP` |
| DOMERLOW | float | [deg C] temperature at dome right, lower | 20.5 | `header.DOMERLOW` |
| DOMERUP | float | [deg C] temperature at dome right, upper | 20.3 | `header.DOMERUP` |
| DOMINPOS | bool | Dome is in position | True | `header.DOMINPOS` |
| DOMLIGHH | str | High dome lights | off | `header.DOMLIGHH` |
| DOMLIGHL | str | Low dome lights | off | `header.DOMLIGHL` |
| DOMSHUTL | str | Lower dome shutter | open | `header.DOMSHUTL` |
| DOMSHUTU | str | Upper dome shutter | open | `header.DOMSHUTU` |
| DOSVER | str | DOS software version | trunk | `header.DOSVER` |
| EPOCH | float | Epoch of observation | 2000.0 | `header.EPOCH` |
| ESTTIME | float | [s] Estimated exposure time for visit (from ETC) | 2056.11 | `header.ESTTIME` |
| ETCFRACB | float | ETC transp. weighted avg. FFRAC (BGS) | 0.134257 | `header.ETCFRACB` |
| ETCFRACE | float | ETC transp. weighted avg. FFRAC (ELG) | 0.295558 | `header.ETCFRACE` |
| ETCFRACP | float | ETC transp. weighted avg. FFRAC (PSF) | 0.380492 | `header.ETCFRACP` |
| ETCPREV | float | [s] ETC cummulative t_eff for visit | 0.0 | `header.ETCPREV` |
| ETCPROF | str | ETC source brightness profile | BGS | `header.ETCPROF` |
| ETCREAL | float | [s] ETC real open shutter time | 1068.442993 | `header.ETCREAL` |
| ETCSEENG | float | [arcsec] ETC seeing | 2.2793 | `header.ETCSEENG` |
| ETCSKY | float | ETC averaged, normalized sky camera flux | 1.973706 | `header.ETCSKY` |
| ETCSKYLV | float | [unit?] ETC skylevel | 1.9356 | `header.ETCSKYLV` |
| ETCSPLIT | int | ETC split sequence number for this visit | 1 | `header.ETCSPLIT` |
| ETCTEFF | float | [s] ETC effective exposure time | 182.517883 | `header.ETCTEFF` |
| ETCTHRUB | float | ETC avg. thruput (BGS profile) | 0.581015 | `header.ETCTHRUB` |
| ETCTHRUE | float | ETC avg. thruput (ELG profile) | 0.589107 | `header.ETCTHRUE` |
| ETCTHRUP | float | ETC avg. thruput (PSF profile) | 0.556269 | `header.ETCTHRUP` |
| ETCTRANS | float | ETC avg. TRANSP normalized to 1 | 0.821598 | `header.ETCTRANS` |
| ETCVERS | str | ETC version | 0.1.21 | `header.ETCVERS` |
| EWALLCMP | float | [deg C] temperature at east wall, computer room | 20.3 | `header.EWALLCMP` |
| EWALLCOU | float | [deg C] temperature at east wall, Coude room | 20.4 | `header.EWALLCOU` |
| EXCLUDED | str | Components excluded from this exposure |  | `header.EXCLUDED` |
| EXPFRAME | int | Guider frame index at exposure start (?) | 0 | `header.EXPFRAME` |
| EXPID | int | Exposure number | 359483 | `header.EXPID` |
| EXPTIME | float | Requested/nominal exposure time (s) | 1065.056 | `header.EXPTIME` |
| EXTNAME | str | Extension name | SPEC | `header.EXTNAME` |
| FFFRMNUM | int | Focus frame number at end of spectro exp. | 17 | `header.FFFRMNUM` |
| FGFRMNUM | int | Guider frame number at end of spectro exp. | 132 | `header.FGFRMNUM` |
| FIBASSGN | str | Fiber assign file | /data/tiles/SVN_tiles/031/fiberassign-031562.fits.gz | `header.FIBASSGN` |
| FIDUCIAL | str | Fiducials status during observation | off | `header.FIDUCIAL` |
| FILENAME | str | Name of (FITS) output file | /exposures/desi/20260702/00359483/desi-00359483.fits.fz | `header.FILENAME` |
| FLAVOR | str | Observation type | science | `header.FLAVOR` |
| FLOOR | float | [deg C] temperature at floor (LCR) | 18.9 | `header.FLOOR` |
| FOCEXPID | int | Focus exposure id at start of spectro exp. | 359483 | `header.FOCEXPID` |
| FOCSTIME | float | [s] focus GFA exposure time | 60.0 | `header.FOCSTIME` |
| FOCUS | str | Telescope focus settings | 1347.3,-187.7,-1309.6,-18.4,32.3,-32.8 | `header.FOCUS` |
| FOCUSCAM | str | Focus cameras used for this exposure | FOCUS1,FOCUS4,FOCUS6,FOCUS9 | `header.FOCUSCAM` |
| FRAMES | NoneType | Number of Frames in Archive | None | `header.FRAMES` |
| FSFRMNUM | int | Sky frame number at end of spectro exp. | 14 | `header.FSFRMNUM` |
| GCOUNT | int | Number of FITS groups (always 1 for a table) | 1 | `header.GCOUNT` |
| GDURATN | float | [s] Duration of guider run | 1108.622 | `header.GDURATN` |
| GFRAMES | int | Number of guider frames for this exposure -- matches count(*) from telemetry.guider_centroids for the same expid | 131 | `header.GFRAMES` |
| GMAXX | float | Guider x-axis maximum offset | 0.814 | `header.GMAXX` |
| GMAXY | float | Guider y-axis maximum offset | 0.5 | `header.GMAXY` |
| GMEANX | float | Guider x-axis mean offsets | 0.319 | `header.GMEANX` |
| GMEANX2 | float | Guider x-axis second moment mean offsets | 0.043 | `header.GMEANX2` |
| GMEANXY | float | Guider cross-axis second moment mean offsets | 0.028 | `header.GMEANXY` |
| GMEANY | float | Guider y-axis mean offsets | 0.089 | `header.GMEANY` |
| GMEANY2 | float | Guider y-axis second moment mean offsets | 0.031 | `header.GMEANY2` |
| GSEEING | float | [arcsec] Guider average seeing | 1.46 | `header.GSEEING` |
| GUIDECAM | str | Comma-separated list of active guide cameras, e.g. GUIDE0,GUIDE2,GUIDE3,GUIDE5,GUIDE7,GUIDE8 | GUIDE0,GUIDE2,GUIDE3,GUIDE5,GUIDE7,GUIDE8 | `header.GUIDECAM` |
| GUIDER | str | jsonb-like summary block embedded in the header: gframes, gseeing, gduration, mean pointing corrections | {'meanx': 0.319, 'meany': 0.089, 'meanx2': 0.043, 'meany2... | `header.GUIDER` |
| GUIDMODE | str | Guider mode | catalog | `header.GUIDMODE` |
| GUIDOFFD | float | [arcsec] DEC guider offset (cummulative, from TCS) | -0.090184 | `header.GUIDOFFD` |
| GUIDOFFR | float | [arcsec] RA guider offset (cummulative, from TCS) | 0.087109 | `header.GUIDOFFR` |
| GUIDTIME | float | Guiding duration (s) | 5.0 | `header.GUIDTIME` |
| GUIEXPID | int | Guider exposure id at start of spectro exp. | 359483 | `header.GUIEXPID` |
| GUST | float | Instantaneous wind gust speed | 11.8 | `header.GUST` |
| HEXPOS | str | Hexapod position | 1347.3,-187.7,-1309.6,-18.4,32.3,-33.0 | `header.HEXPOS` |
| HEXTRIM | str | Hexapod trim values | 0.0,0.0,0.0,0.0,0.0,0.0 | `header.HEXTRIM` |
| HUMIDITY | float | [%] (outside) humidity | 10.2 | `header.HUMIDITY` |
| IFFRMNUM | int | Focus frame number at start of spectro exp. | 0 | `header.IFFRMNUM` |
| IGFRMNUM | int | Guider frame number at start of spectro exp. | 5 | `header.IGFRMNUM` |
| ILLSPECS | str | Participating illuminate spectrographs | SP0,SP1,SP2,SP3,SP4,SP5,SP6,SP7,SP8,SP9 | `header.ILLSPECS` |
| INAMPS | float | [A] UPS total input current | 71.1 | `header.INAMPS` |
| INCTRL | bool | DESI in control | True | `header.INCTRL` |
| INIFILE | str | DOS Configuration file | /data/msdos/dos_home/architectures/kpno/desi_refactored.ini | `header.INIFILE` |
| INPOS | bool | Mount in position | True | `header.INPOS` |
| INSTRUME | str | Instrument name | DESI | `header.INSTRUME` |
| ISFRMNUM | int | Sky frame number at start of spectro exp. | 0 | `header.ISFRMNUM` |
| KEEPFOCS | bool | DOS Control: keep focus running | False | `header.KEEPFOCS` |
| KEEPGUDR | bool | DOS Control: keep guider running | False | `header.KEEPGUDR` |
| KEEPSKY | bool | DOS Control: keep sky mon. running | False | `header.KEEPSKY` |
| LEAD | str | Lead observer | Luke Tyas | `header.LEAD` |
| MANIFEST | bool | DOS exposure manifest | False | `header.MANIFEST` |
| MAXSPLIT | int | Number of allowed exposure splits | 0 | `header.MAXSPLIT` |
| MAXTIME | float | [s] Maximum exposure time for entire visit (from NTS) | 5400.0 | `header.MAXTIME` |
| MIDTIME | float | [s] Exposure midpoint time used by PlateMaker | 915.0 | `header.MIDTIME` |
| MINTIME | float | [s] Minimum exposure time (from NTS, used by ETC) | 180.0 | `header.MINTIME` |
| MJD-OBS | float | Modified Julian Date of observation | 61224.173444018 | not expressible as `header.MJD-OBS` -- hyphen breaks resolve_spec's identifier syntax; use a callable, e.g. `lambda exp: exp.header['MJD-OBS']` |
| MNTOFFD | float | [arcsec] DEC mMount offset (GFAPROC pointing corr.) | 38.78 | `header.MNTOFFD` |
| MNTOFFR | float | [arcsec] RA mount offset (GFAPROC pointing corr.) | 8.39 | `header.MNTOFFR` |
| MODULE | str | Image Sources/Component | CI | `header.MODULE` |
| MOONDEC | float | [deg] Moon declination at start of exposure | -17.212429 | `header.MOONDEC` |
| MOONRA | float | [deg] Moon RA at start of exposure | 318.954513 | `header.MOONRA` |
| MOONSEP | float | [deg] Moon Separation | 100.429 | `header.MOONSEP` |
| MOUNTAZ | float | Mount azimuth | 202.864377 | `header.MOUNTAZ` |
| MOUNTDEC | float | [deg] Mount declination | -9.0164 | `header.MOUNTDEC` |
| MOUNTEL | float | Mount elevation | 46.339571 | `header.MOUNTEL` |
| MOUNTHA | float | Mount hour angle | 15.759805 | `header.MOUNTHA` |
| NAXIS | int | Number of axes | 2 | `header.NAXIS` |
| NAXIS1 | int | Number of pixels (columns) | 8 | `header.NAXIS1` |
| NAXIS2 | int | Number of pixels (rows) | 1 | `header.NAXIS2` |
| NFSAZRNG | str | NFS AZ Range Constraint | -180.0, 180.0 | `header.NFSAZRNG` |
| NFSELRNG | str | NFS EL Range Constraint | 0.0, 90.0 | `header.NFSELRNG` |
| NFSSTAFA | bool | NFS Static FA Constraint | False | `header.NFSSTAFA` |
| NIGHT | int | Observing night | 20260702 | `header.NIGHT` |
| NTSPROG | str | NTS program name | BRIGHT | `header.NTSPROG` |
| NTSSURVY | str | NTS survey name | main | `header.NTSSURVY` |
| NWALLIN | float | [deg C] temperature at north wall inside | 19.1 | `header.NWALLIN` |
| NWALLOUT | float | [deg C] temperature at north wall outside | 20.4 | `header.NWALLOUT` |
| OBJECT | str | Object name |  | `header.OBJECT` |
| OBS-ELEV | float | [m] Observatory elevation | 2097.0 | not expressible as `header.OBS-ELEV` -- hyphen breaks resolve_spec's identifier syntax; use a callable, e.g. `lambda exp: exp.header['OBS-ELEV']` |
| OBS-LAT | str | [deg] Observatory latitude | 31.96403 | not expressible as `header.OBS-LAT` -- hyphen breaks resolve_spec's identifier syntax; use a callable, e.g. `lambda exp: exp.header['OBS-LAT']` |
| OBS-LONG | str | [deg] Observatory east longitude | -111.59989 | not expressible as `header.OBS-LONG` -- hyphen breaks resolve_spec's identifier syntax; use a callable, e.g. `lambda exp: exp.header['OBS-LONG']` |
| OBSERVAT | str | Observatory name | KPNO | `header.OBSERVAT` |
| OBSERVER | str | Names of observers | Edwin Perez, Shufei Liu | `header.OBSERVER` |
| OBSTYPE | str | Spectrograph observation type | SCIENCE | `header.OBSTYPE` |
| OCSVER | float | OCS software version | 1.2 | `header.OCSVER` |
| OPENSHUT | str | [s] Time shutter opened | 2026-07-03T04:09:46.164148 | `header.OPENSHUT` |
| OUTTEMP | float | [deg C] outside temperature | 20.4 | `header.OUTTEMP` |
| OUTWATTS | str | [W] UPS Phase A, B, C output watts | 4900.0,7400.0,4900.0 | `header.OUTWATTS` |
| PARALLAC | float | [deg] Parallactic angle | 19.698296 | `header.PARALLAC` |
| PCOUNT | int | Number of parameter bytes (FITS table heap size) | 6 | `header.PCOUNT` |
| PETALS | str | Participating petals | PETAL0,PETAL1,PETAL2,PETAL3,PETAL4,PETAL5,PETAL6,PETAL7,P... | `header.PETALS` |
| PLATFORM | float | [deg C] temperature at platform | 20.3 | `header.PLATFORM` |
| PMCOOL | str | Primary mirror cooling | off | `header.PMCOOL` |
| PMCOVER | str | Primary mirror cover | open | `header.PMCOVER` |
| PMIRTEMP | float | Primary mirror temperature (platemaker/telemetry snapshot) | 17.625 | `header.PMIRTEMP` |
| PMREADY | bool | Primary mirror ready | True | `header.PMREADY` |
| PMSEEING | float | Platemaker-measured seeing | 2.2975 | `header.PMSEEING` |
| PMTRANSP | NoneType | [%] PlateMaker GFAPROC transparency | None | `header.PMTRANSP` |
| PMVER | str | PlateMaker/Dervish version | not available | `header.PMVER` |
| POSCNVGD | int | Number of positioners converged | 604 | `header.POSCNVGD` |
| POSCVFRC | float | Fraction of converged positioners | 0.1392 | `header.POSCVFRC` |
| POSCYCLE | int | Number of current iteration | 1 | `header.POSCYCLE` |
| POSDISAB | int | Number of disabled positioners | 639 | `header.POSDISAB` |
| POSENABL | int | Number of enabled positioners | 4340 | `header.POSENABL` |
| POSFRACT | float |  | 0.95 | `header.POSFRACT` |
| POSITER | int | Positioning Control: max. number of pos. cycles | 1 | `header.POSITER` |
| POSMVALL | bool | Positioning Control: move all positioners | True | `header.POSMVALL` |
| POSNOTON | int | Number of enabled positioners not on target | 102 | `header.POSNOTON` |
| POSONFRC | float | Fraction of positioners on target | 0.9774 | `header.POSONFRC` |
| POSONTGT | int | Number of positioners on target | 4242 | `header.POSONTGT` |
| POSRMS | float | [mm] RMS of positioner accuracy | 0.0042 | `header.POSRMS` |
| POSTOLER | float | Positioning Control: in_position tolerance (mm) | 0.002 | `header.POSTOLER` |
| PRESSURE | float | [torr] (outside) air pressure | 794.4 | `header.PRESSURE` |
| PROGRAM | str | Program name | BACKUP | `header.PROGRAM` |
| PROPID | str | Proposal ID | 2020B-5000 | `header.PROPID` |
| PURPOSE | str | Purpose of observing night | Main Survey | `header.PURPOSE` |
| RADESYS | str | Coordinate reference frame of major/minor axes | FK5 | `header.RADESYS` |
| REACQUIR | bool | DOS Control: reacquire same files | False | `header.REACQUIR` |
| REQADC | str | [deg] requested ADC angles | 348.68,54.26 | `header.REQADC` |
| REQDEC | float | [deg] Requested declination (observer input) | -9.006 | `header.REQDEC` |
| REQRA | float | [deg] Requested right ascension (observer input) | 216.12 | `header.REQRA` |
| REQTEFF | float | [s] Requested effective exposure time | 180.0 | `header.REQTEFF` |
| REQTIME | float | [s] Requested exposure time | 1860.0 | `header.REQTIME` |
| RESETROT | bool | DOS Control: reset hex rotator | False | `header.RESETROT` |
| ROOF | float | [deg C] temperature on roof | 20.8 | `header.ROOF` |
| ROOFAMB | float | [deg C] ambient temperature on roof | 20.4 | `header.ROOFAMB` |
| ROTENBLD | bool | Rotator enabled | True | `header.ROTENBLD` |
| ROTOFFST | float | [arcsec] Rotator offset | -33.0 | `header.ROTOFFST` |
| ROTRATE | float | [arcsec/min] Rotator rate | 0.409 | `header.ROTRATE` |
| SBPROF | str | Profile used by ETC | BGS | `header.SBPROF` |
| SEANNEX | bool | Telescope is at SE annex | False | `header.SEANNEX` |
| SECLEFT | float | [s] UPS Seconds left | 4596.0 | `header.SECLEFT` |
| SEEING | float | [arcsec] ETC/PM seeing | 2.2975 | `header.SEEING` |
| SEQNUM | int | Number of exposure in sequence | 1 | `header.SEQNUM` |
| SEQSTART | str | Start time of sequence processing | 2026-07-03T04:06:04.925575 | `header.SEQSTART` |
| SEQUENCE | str | Exposure sequence type, e.g. 'DESI' for science exposures | DESI | `header.SEQUENCE` |
| SHACKC | float | [deg C] temperature at shack ceiling | 19.6 | `header.SHACKC` |
| SHACKW | float | [deg C] temperature at shack wall | 19.1 | `header.SHACKW` |
| SIMGFACQ | bool |  | False | `header.SIMGFACQ` |
| SIMGFAP | bool | DOS Control: simulate GFAPROC | False | `header.SIMGFAP` |
| SKYCAM | str | Sky cameras used for this exposure | SKYCAM0,SKYCAM1 | `header.SKYCAM` |
| SKYDEC | float | Sky-pointing Dec (deg) | -9.0164 | `header.SKYDEC` |
| SKYEXPID | int | Sky exposure id at start of spectro exp. | 359430 | `header.SKYEXPID` |
| SKYLEVEL | float | Sky brightness level | 1.88 | `header.SKYLEVEL` |
| SKYRA | float | Sky-pointing RA (deg) | 216.11585 | `header.SKYRA` |
| SKYTIME | float | [s] sky camera exposure time (acquisition) | 60.0 | `header.SKYTIME` |
| SLEWANGL | float | [deg] Slew Angle | 41.921 | `header.SLEWANGL` |
| SLEWTIME | float | [s] Slew Time | 112.782 | `header.SLEWTIME` |
| SP0BLUP | float | [mb] SP0 blue pressure | 1.047e-07 | `header.SP0BLUP` |
| SP0BLUT | float | [K] SP0 blue temperature | 162.99 | `header.SP0BLUT` |
| SP0NIRP | float | [mb] SP0 NIR pressure | 7.893e-08 | `header.SP0NIRP` |
| SP0NIRT | float | [K] SP0 NIR temperature | 140.03 | `header.SP0NIRT` |
| SP0REDP | float | [mb] SP0 red pressure | 1.191e-07 | `header.SP0REDP` |
| SP0REDT | float | [K] SP0 red temperature | 163.07 | `header.SP0REDT` |
| SP1BLUP | float | [mb] SP1 blue pressure | 9.229e-08 | `header.SP1BLUP` |
| SP1BLUT | float | [K] SP1 blue temperature | 163.02 | `header.SP1BLUT` |
| SP1NIRP | float | [mb] SP1 NIR pressure | 9.955e-08 | `header.SP1NIRP` |
| SP1NIRT | float | [K] SP1 NIR temperature | 125.14 | `header.SP1NIRT` |
| SP1REDP | float | [mb] SP1 red pressure | 1.167e-07 | `header.SP1REDP` |
| SP1REDT | float | [K] SP1 red temperature | 162.99 | `header.SP1REDT` |
| SP2BLUP | float | [mb] SP2 blue pressure | 1.376e-07 | `header.SP2BLUP` |
| SP2BLUT | float | [K] SP2 blue temperature | 163.04 | `header.SP2BLUT` |
| SP2NIRP | float | [mb] SP2 NIR pressure | 5.84e-08 | `header.SP2NIRP` |
| SP2NIRT | float | [K] SP2 NIR temperature | 125.14 | `header.SP2NIRT` |
| SP2REDP | float | [mb] SP2 red pressure | 7.096e-08 | `header.SP2REDP` |
| SP2REDT | float | [K] SP2 red temperature | 140.11 | `header.SP2REDT` |
| SP3BLUP | float | [mb] SP3 blue pressure | 1.18e-07 | `header.SP3BLUP` |
| SP3BLUT | float | [K] SP3 blue temperature | 162.97 | `header.SP3BLUT` |
| SP3NIRP | float | [mb] SP3 NIR pressure | 5.199e-07 | `header.SP3NIRP` |
| SP3NIRT | float | [K] SP3 NIR temperature | 140.13 | `header.SP3NIRT` |
| SP3REDP | float | [mb] SP3 red pressure | 6.761e-08 | `header.SP3REDP` |
| SP3REDT | float | [K] SP3 red temperature | 140.03 | `header.SP3REDT` |
| SP4BLUP | float | [mb] SP4 blue pressure | 1.252e-07 | `header.SP4BLUP` |
| SP4BLUT | float | [K] SP4 blue temperature | 162.99 | `header.SP4BLUT` |
| SP4NIRP | float | [mb] SP4 NIR pressure | 7.782e-08 | `header.SP4NIRP` |
| SP4NIRT | float | [K] SP4 NIR temperature | 139.99 | `header.SP4NIRT` |
| SP4REDP | float | [mb] SP4 red pressure | 7.679e-08 | `header.SP4REDP` |
| SP4REDT | float | [K] SP4 red temperature | 140.11 | `header.SP4REDT` |
| SP5BLUP | float | [mb] SP5 blue pressure | 1.236e-07 | `header.SP5BLUP` |
| SP5BLUT | float | [K] SP5 blue temperature | 163.04 | `header.SP5BLUT` |
| SP5NIRP | float | [mb] SP5 NIR pressure | 7.552e-08 | `header.SP5NIRP` |
| SP5NIRT | float | [K] SP5 NIR temperature | 140.13 | `header.SP5NIRT` |
| SP5REDP | float | [mb] SP5 red pressure | 6.175e-08 | `header.SP5REDP` |
| SP5REDT | float | [K] SP5 red temperature | 121.13 | `header.SP5REDT` |
| SP6BLUP | float | [mb] SP6 blue pressure | 1.087e-07 | `header.SP6BLUP` |
| SP6BLUT | float | [K] SP6 blue temperature | 163.02 | `header.SP6BLUT` |
| SP6NIRP | float | [mb] SP6 NIR pressure | 1.296e-07 | `header.SP6NIRP` |
| SP6NIRT | float | [K] SP6 NIR temperature | 140.06 | `header.SP6NIRT` |
| SP6REDP | float | [mb] SP6 red pressure | 7.143e-08 | `header.SP6REDP` |
| SP6REDT | float | [K] SP6 red temperature | 140.08 | `header.SP6REDT` |
| SP7BLUP | float | [mb] SP7 blue pressure | 1.375e-07 | `header.SP7BLUP` |
| SP7BLUT | float | [K] SP7 blue temperature | 162.97 | `header.SP7BLUT` |
| SP7NIRP | float | [mb] SP7 NIR pressure | 5.542e-08 | `header.SP7NIRP` |
| SP7NIRT | float | [K] SP7 NIR temperature | 140.13 | `header.SP7NIRT` |
| SP7REDP | float | [mb] SP7 red pressure | 1.176e-07 | `header.SP7REDP` |
| SP7REDT | float | [K] SP7 red temperature | 163.07 | `header.SP7REDT` |
| SP8BLUP | float | [mb] SP8 blue pressure | 9.36e-08 | `header.SP8BLUP` |
| SP8BLUT | float | [K] SP8 blue temperature | 162.92 | `header.SP8BLUT` |
| SP8NIRP | float | [mb] SP8 NIR pressure | 7.465e-08 | `header.SP8NIRP` |
| SP8NIRT | float | [K] SP8 NIR temperature | 140.06 | `header.SP8NIRT` |
| SP8REDP | float | [mb] SP8 red pressure | 4.978e-08 | `header.SP8REDP` |
| SP8REDT | float | [K] SP8 red temperature | 139.99 | `header.SP8REDT` |
| SP9BLUP | float | [mb] SP9 blue pressure | 8.613e-08 | `header.SP9BLUP` |
| SP9BLUT | float | [K] SP9 blue temperature | 162.99 | `header.SP9BLUT` |
| SP9NIRP | float | [mb] SP9 NIR pressure | 6.556e-08 | `header.SP9NIRP` |
| SP9NIRT | float | [K] SP9 NIR temperature | 140.03 | `header.SP9NIRT` |
| SP9REDP | float | [mb] SP9 red pressure | 1.493e-07 | `header.SP9REDP` |
| SP9REDT | float | [K] SP9 red temperature | 163.07 | `header.SP9REDT` |
| SPCGRPHS | str | Participating spectrographs | SP0,SP1,SP2,SP3,SP4,SP5,SP6,SP7,SP8,SP9 | `header.SPCGRPHS` |
| SPLITEXP | bool | Whether this exposure was split (cosmic-ray splitting) | False | `header.SPLITEXP` |
| ST | str | Local Sidereal time at observation start (HH:MM:SS) | 15:28:11.371000 | `header.ST` |
| STAIRSL | float | [deg C] temperature at stairs, lower | 19.9 | `header.STAIRSL` |
| STAIRSM | float | [deg C] temperature at stairs, mid | 20.0 | `header.STAIRSM` |
| STAIRSU | float | [deg C] temperature at stairs, upper | 20.2 | `header.STAIRSU` |
| STARTADJ | str | Time sequence starts adjusting the instrument | 2026-07-03T04:06:16.324266 | `header.STARTADJ` |
| STOPFOCS | bool | DOS Control: stop focus | True | `header.STOPFOCS` |
| STOPGUDR | bool | DOS Control: stop guider | True | `header.STOPGUDR` |
| STOPSKY | bool | DOS Control: stop sky monitor | True | `header.STOPSKY` |
| SUNDEC | float | [deg] Sun declination at start of exposure | 22.957743 | `header.SUNDEC` |
| SUNRA | float | [deg] Sun RA at start of exposure | 102.257424 | `header.SUNRA` |
| TAIRFLOW | float | Telescope air flow | 0.0 | `header.TAIRFLOW` |
| TAIRITMP | float | [deg] Telescope air in temperature | 14.6 | `header.TAIRITMP` |
| TAIROTMP | float | [deg] Telescope air out temperature | 18.1 | `header.TAIROTMP` |
| TAIRTEMP | float | Air temperature (snapshot) | 20.262 | `header.TAIRTEMP` |
| TARGTAZ | float | [deg] Target azimuth | 203.103557 | `header.TARGTAZ` |
| TARGTDEC | float | [deg] Target declination (to TCS) | -9.0164 | `header.TARGTDEC` |
| TARGTEL | float | [deg] Target elevation | 46.280747 | `header.TARGTEL` |
| TARGTRA | float | [deg] Target right ascension (to TCS) | 216.11585 | `header.TARGTRA` |
| TCASITMP | float | [deg] Telescope Cass Cage in temperature | 6.6 | `header.TCASITMP` |
| TCASOTMP | float | [deg] Telescope Cass Cage out temperature | 21.2 | `header.TCASOTMP` |
| TCIBTEMP | float | [deg] Telescope chimney IB temperature | 0.0 | `header.TCIBTEMP` |
| TCIMTEMP | float | [deg] Telescope chimney IM temperature | 0.0 | `header.TCIMTEMP` |
| TCITTEMP | float | [deg] Telescope chimney IT temperature | 17.7 | `header.TCITTEMP` |
| TCOSTEMP | float | [deg] Telescope chimney OS temperature | 0.0 | `header.TCOSTEMP` |
| TCOWTEMP | float | [deg] Telescope chimney OW temperature | 0.0 | `header.TCOWTEMP` |
| TCSGDEC | float | TCS simple gain (dec) | 0.15 | `header.TCSGDEC` |
| TCSGRA | float | TCS simple gain (RA) | 0.15 | `header.TCSGRA` |
| TCSITEMP | float | [deg] Telescope center section in temperature | 18.4 | `header.TCSITEMP` |
| TCSKDEC | str | TCS Kalman (dec) | 0 0 0 | `header.TCSKDEC` |
| TCSKRA | str | TCS Kalman (RA) | 0 0 0 | `header.TCSKRA` |
| TCSMFDEC | int | TCS moving filter length (dec) | 2 | `header.TCSMFDEC` |
| TCSMFRA | int | TCS moving filter length (RA) | 2 | `header.TCSMFRA` |
| TCSMJD | float | MJD reported by TCS | 61224.173889 | `header.TCSMJD` |
| TCSOTEMP | float | [deg] Telescope center section out temperature | 21.2 | `header.TCSOTEMP` |
| TCSPIDEC | str | TCS PI settings (P, I (gain, error window, saturation) (dec) | 1.0,0.0,0.0,0.0 | `header.TCSPIDEC` |
| TCSPIRA | str | TCS PI settings (P, I (gain, error window, saturation) (RA) | 1.0,0.0,0.0,0.0 | `header.TCSPIRA` |
| TCSST | str | Local Sidereal time reported by TCS (HH:MM:SS) | 15:28:12.774 | `header.TCSST` |
| TDBTEMP | float | [deg] Telescope dec bore temperature | 18.5 | `header.TDBTEMP` |
| TDEWPNT | float | Telescope air dew point | -8.847 | `header.TDEWPNT` |
| TELBASE | float | [deg C] temperature at telescope base | 20.1 | `header.TELBASE` |
| TELESCOP | str | Telescope name | KPNO 4.0-m telescope | `header.TELESCOP` |
| TFIELDS | int | Number of table columns | 1 | `header.TFIELDS` |
| TFLOWIN | float | Telescope flow rate in | 0.0 | `header.TFLOWIN` |
| TFLOWOUT | float | Telescope flow rate out | 0.0 | `header.TFLOWOUT` |
| TFORM1 | str |  | 1PB(6) | `header.TFORM1` |
| TGFAPROC | float | [s] PlateMaker GFAPROC processing time | 4.4815 | `header.TGFAPROC` |
| TGLYCOLI | float | [deg] Telescope glycol in temperature | 6.4 | `header.TGLYCOLI` |
| TGLYCOLO | float | [deg] Telescope glycol out temperature | 9.5 | `header.TGLYCOLO` |
| THINGES | float | [deg] Telescope hinge S temperature | 21.4 | `header.THINGES` |
| THINGEW | float | [deg] Telescope hinge W temperature | 22.3 | `header.THINGEW` |
| TILEDEC | float | DEC of tile given in fiberassign file | -9.006 | `header.TILEDEC` |
| TILEID | int | DESI Tile ID | 31562 | `header.TILEID` |
| TILERA | float | RA of tile given in fiberassign file | 216.12 | `header.TILERA` |
| TIME-OBS | str | [UTC] Observation start time | 04:09:45.563203 | not expressible as `header.TIME-OBS` -- hyphen breaks resolve_spec's identifier syntax; use a callable, e.g. `lambda exp: exp.header['TIME-OBS']` |
| TIMESYS | str | Time system used for date-obs | UTC | `header.TIMESYS` |
| TNFSPROC | float | [s] PlateMaker NFSPROC processing time | 6.8169 | `header.TNFSPROC` |
| TOTTEFF | float | [s] Total effective exposure time for visit | 182.0525 | `header.TOTTEFF` |
| TPCITEMP | float | [deg] Telescope primary cell in temperature | 17.4 | `header.TPCITEMP` |
| TPCOTEMP | float | [deg] Telescope primary cell out temperature | 17.8 | `header.TPCOTEMP` |
| TPMAVERT | float | [deg] Telescope mirror averagetemperature | 17.578 | `header.TPMAVERT` |
| TPMDESIT | float | [deg] Telescope mirror desired temperature | 16.0 | `header.TPMDESIT` |
| TPMEIBT | float | [deg] Telescope mirror EIB temperature | 17.8 | `header.TPMEIBT` |
| TPMEITT | float | [deg] Telescope mirror EIT temperature | 17.6 | `header.TPMEITT` |
| TPMEOBT | float | [deg] Telescope mirror EOB temperature | 17.6 | `header.TPMEOBT` |
| TPMEOTT | float | [deg] Telescope mirror EOT temperature | 18.2 | `header.TPMEOTT` |
| TPMNIBT | float | [deg] Telescope mirror NIB temperature | 19.24 | `header.TPMNIBT` |
| TPMNITT | float | [deg] Telescope mirror NIT temperature | 17.5 | `header.TPMNITT` |
| TPMNOBT | float | [deg] Telescope mirror NOB temperature | 17.5 | `header.TPMNOBT` |
| TPMNOTT | float | [deg] Telescope mirror NOT temperature | 18.3 | `header.TPMNOTT` |
| TPMRTDT | float | [deg] Telescope mirror RTD temperature | 19.24 | `header.TPMRTDT` |
| TPMSIBT | float | [deg] Telescope mirror SIB temperature | 17.5 | `header.TPMSIBT` |
| TPMSITT | float | [deg] Telescope mirror SIT temperature | 17.6 | `header.TPMSITT` |
| TPMSOBT | float | [deg] Telescope mirror SOB temperature | 17.2 | `header.TPMSOBT` |
| TPMSOTT | float | [deg] Telescope mirror SOT temperature | 17.9 | `header.TPMSOTT` |
| TPMSTAT | str | Telescope mirror status | ready | `header.TPMSTAT` |
| TPMWIBT | float | [deg] Telescope mirror WIB temperature | 17.2 | `header.TPMWIBT` |
| TPMWITT | float | [deg] Telescope mirror WIT temperature | 17.4 | `header.TPMWITT` |
| TPMWOBT | float | [deg] Telescope mirror WOB temperature | 16.5 | `header.TPMWOBT` |
| TPMWOTT | float | [deg] Telescope mirror WOT temperature | 17.1 | `header.TPMWOTT` |
| TPR1HUM | float | Telescope probe 1 humidity | 0.0 | `header.TPR1HUM` |
| TPR1TEMP | float | [deg] Telescope probe1 temperature | 0.0 | `header.TPR1TEMP` |
| TPR2HUM | float | Telescope probe 2 humidity | 0.0 | `header.TPR2HUM` |
| TPR2TEMP | float | [deg] Telescope probe2 temperature | 0.0 | `header.TPR2TEMP` |
| TRANSPAR | NoneType | ETC/PM transparency | None | `header.TRANSPAR` |
| TRGTOFFD | float | [arcsec] Telescope target offset (dec) | 0.0 | `header.TRGTOFFD` |
| TRGTOFFR | float | [arcsec] Telescope target offset (RA) | 0.0 | `header.TRGTOFFR` |
| TRUSTEMP | float | [deg] Average Telescope truss temperature (only tsb, tsm, tst) | 21.833 | `header.TRUSTEMP` |
| TSERVO | float | Telescope servo setpoint | 40.0 | `header.TSERVO` |
| TTRSTEMP | float | [deg] Telescope top ring S temperature | 21.6 | `header.TTRSTEMP` |
| TTRUETBT | float | [deg] Telescope truss ETB temperature | 14.5 | `header.TTRUETBT` |
| TTRUETTT | float | [deg] Telescope truss ETT temperature | 22.3 | `header.TTRUETTT` |
| TTRUNTBT | float | [deg] Telescope truss NTB temperature | 21.5 | `header.TTRUNTBT` |
| TTRUNTTT | float | [deg] Telescope truss NTT temperature | 22.3 | `header.TTRUNTTT` |
| TTRUSTBT | float | [deg] Telescope truss STB temperature | 21.3 | `header.TTRUSTBT` |
| TTRUSTST | float | [deg] Telescope truss STS temperature | 10.8 | `header.TTRUSTST` |
| TTRUSTTT | float | [deg] Telescope truss STT temperature | 21.5 | `header.TTRUSTTT` |
| TTRUTSBT | float | [deg] Telescope truss TSB temperature | 21.8 | `header.TTRUTSBT` |
| TTRUTSMT | float | [deg] Telescope truss TSM temperature | 21.9 | `header.TTRUTSMT` |
| TTRUTSTT | float | [deg] Telescope truss TST temperature | 22.4 | `header.TTRUTSTT` |
| TTRUWTBT | float | [deg] Telescope truss WTB temperature | 21.2 | `header.TTRUWTBT` |
| TTRUWTTT | float | [deg] Telescope truss WTT temperature | 22.1 | `header.TTRUWTTT` |
| TTRWTEMP | float | [deg] Telescope top ring W temperature | 21.1 | `header.TTRWTEMP` |
| TTYPE1 | str |  | COMPRESSED_DATA | `header.TTYPE1` |
| TURBCLIP | int |  | 79 | `header.TURBCLIP` |
| TURBRMS | float | [mm] RMS of turbulence correction | 0.0085 | `header.TURBRMS` |
| UPSSTAT | str | UPS Status | System Normal - On Line(7) | `header.UPSSTAT` |
| USEDONUT | bool | DOS Control: use donuts | True | `header.USEDONUT` |
| USEETC | bool | ETC data available if true | True | `header.USEETC` |
| USEFID | bool | DOS Control: use fiducials | True | `header.USEFID` |
| USEFOCUS | bool | DOS Control: use focus | True | `header.USEFOCUS` |
| USEFVC | bool | DOS Control: use fvc | True | `header.USEFVC` |
| USEGUIDR | bool | DOS Control: use guider | True | `header.USEGUIDR` |
| USEILLUM | bool | DOS Control: use illuminator | True | `header.USEILLUM` |
| USEMIDPT | bool | Use exposure midpoint if true | True | `header.USEMIDPT` |
| USEOPENL | bool | DOS Control: use open loop move | True | `header.USEOPENL` |
| USEPOS | bool | Fiber positioner data available if true | True | `header.USEPOS` |
| USEROTAT | bool | DOS Control: use rotator | True | `header.USEROTAT` |
| USESKY | bool | DOS Control: use Sky Monitor | True | `header.USESKY` |
| USESPCTR | bool | DOS Control: use spectrographs | True | `header.USESPCTR` |
| USESPLIT | bool | Exposure splits are allowed | True | `header.USESPLIT` |
| USESPTTK | bool | DOS Control: use spottrack | False | `header.USESPTTK` |
| USETURB | bool | Turbulence corrections are applied if true | True | `header.USETURB` |
| USEXSRVR | bool | DOS Control: use exposure server | True | `header.USEXSRVR` |
| UTILROOM | float | [deg C] temperature in utilitiy room | 19.4 | `header.UTILROOM` |
| UTILWALL | float | [deg C] temperature at utility room wall | 20.5 | `header.UTILWALL` |
| VCCD | str | True (ON) if CCD voltage is on | ON | `header.VCCD` |
| VISITIDS | str | List of expids for a visit (same tile) | 359483 | `header.VISITIDS` |
| WHITESPT | bool | Telescope is at whitespot | False | `header.WHITESPT` |
| WINDDIR | float | Instantaneous wind direction | 174.5 | `header.WINDDIR` |
| WINDSPD | float | Instantaneous wind speed at exposure time (header snapshot, not a telemetry average) | 11.9 | `header.WINDSPD` |
| WWALLIN | float | [deg C] temperature at west wall inside | 19.4 | `header.WWALLIN` |
| WWALLOUT | float | [deg C] temperature at west wall outside | 20.3 | `header.WWALLOUT` |
| XTENSION | str | FITS extension type (e.g. BINTABLE, IMAGE) | BINTABLE | `header.XTENSION` |
| ZBITPIX | int |  | 16 | `header.ZBITPIX` |
| ZCMPTYPE | str | FITS tile-compression algorithm used | RICE_1 | `header.ZCMPTYPE` |
| ZD | float | [deg] Telescope zenith distance | 43.719253 | `header.ZD` |
| ZENITH | bool | Telescope is at zenith | False | `header.ZENITH` |
| ZIMAGE | bool |  | True | `header.ZIMAGE` |
| ZNAME1 | str | Tile-compression parameter 1 name | BLOCKSIZE | `header.ZNAME1` |
| ZNAME2 | str | Tile-compression parameter 2 name | BYTEPIX | `header.ZNAME2` |
| ZNAXIS | int |  | 1 | `header.ZNAXIS` |
| ZNAXIS1 | int |  | 10 | `header.ZNAXIS1` |
| ZSIMPLE | bool |  | True | `header.ZSIMPLE` |
| ZTILE1 | int |  | 10 | `header.ZTILE1` |
| ZVAL1 | int | Tile-compression parameter 1 value | 32 | `header.ZVAL1` |
| ZVAL2 | int | Tile-compression parameter 2 value | 2 | `header.ZVAL2` |


## Exposure directory: `coordinates-<expid>.fits` (`DATA` extension)

One row per fiber, indexed by (PETAL_LOC, DEVICE_LOC) once read via `fits_io.read_coordinates`.

| Field | Type | Description | Example value | Source |
|---|---|---|---|---|
| PETAL_LOC | >i8 |  | 4 | `coords['PETAL_LOC']` (per-fiber table) |
| DEVICE_LOC | >i8 |  | 25 | `coords['DEVICE_LOC']` (per-fiber table) |
| POS_Q | >f8 | Fiber positioner theta arm angle | 62.6078714537288 | `coords['POS_Q']` (per-fiber table) |
| POS_S | >f8 | Fiber positioner phi arm angle | 89.16406750003033 | `coords['POS_S']` (per-fiber table) |
| POS_FLAGS | >f8 | Positioner status bitmask | 16842756.0 | `coords['POS_FLAGS']` (per-fiber table) |
| POS_X | >f8 | Fiber X position, focal-plane coords | 41.020101682497774 | `coords['POS_X']` (per-fiber table) |
| POS_Y | >f8 | Fiber Y position, focal-plane coords | 79.16241488372437 | `coords['POS_Y']` (per-fiber table) |
| POS_LINPHI | <U5 | Whether this positioner's phi arm is in the 'linear' calibration regime | False | `coords['POS_LINPHI']` (per-fiber table) |
| POS_ID | <U6 |  | M00283 | `coords['POS_ID']` (per-fiber table) |
| TARGET_RA | >f8 | Target RA from fiberassign | 215.95043141357516 | `coords['TARGET_RA']` (per-fiber table) |
| TARGET_DEC | >f8 | Target Dec from fiberassign | -8.680371491658748 | `coords['TARGET_DEC']` (per-fiber table) |
| FA_X | >f4 |  | 41.020092 | `coords['FA_X']` (per-fiber table) |
| FA_Y | >f4 |  | 79.16241 | `coords['FA_Y']` (per-fiber table) |
| FA_FIBER | >f8 |  | 2107.0 | `coords['FA_FIBER']` (per-fiber table) |
| REQ_Q | >f8 |  | 62.595 | `coords['REQ_Q']` (per-fiber table) |
| REQ_S | >f8 |  | 89.144 | `coords['REQ_S']` (per-fiber table) |
| REQ_X | >f8 |  | 41.029 | `coords['REQ_X']` (per-fiber table) |
| REQ_Y | >f8 |  | 79.135 | `coords['REQ_Y']` (per-fiber table) |
| EXP_Q_0 | >f8 |  | 62.6078714537288 | `coords['EXP_Q_0']` (per-fiber table) |
| EXP_S_0 | >f8 |  | 89.16406750003033 | `coords['EXP_S_0']` (per-fiber table) |
| FLAGS_EXP_0 | >i8 |  | 16842756 | `coords['FLAGS_EXP_0']` (per-fiber table) |
| EXP_X_0 | >f8 |  | 41.020101682497774 | `coords['EXP_X_0']` (per-fiber table) |
| EXP_Y_0 | >f8 |  | 79.16241488372437 | `coords['EXP_Y_0']` (per-fiber table) |
| FVC_X_0 | >f8 |  | -288.707 | `coords['FVC_X_0']` (per-fiber table) |
| FVC_Y_0 | >f8 |  | 554.867 | `coords['FVC_Y_0']` (per-fiber table) |
| FLAGS_FVC_0 | >i8 |  | 16842756 | `coords['FLAGS_FVC_0']` (per-fiber table) |
| CNT_X_0 | >f8 |  | -286.82000000000016 | `coords['CNT_X_0']` (per-fiber table) |
| CNT_Y_0 | >f8 |  | 551.3829999999998 | `coords['CNT_Y_0']` (per-fiber table) |
| FLAGS_CNT_0 | >i8 |  | 16842821 | `coords['FLAGS_CNT_0']` (per-fiber table) |
| CNT_MAG_0 | >f8 |  | 13.331 | `coords['CNT_MAG_0']` (per-fiber table) |
| CNT_ERR_0 | >f8 |  | 0.001 | `coords['CNT_ERR_0']` (per-fiber table) |
| DX_0 | >f8 |  | 0.006380328422086341 | `coords['DX_0']` (per-fiber table) |
| DY_0 | >f8 |  | -0.013355827626028053 | `coords['DY_0']` (per-fiber table) |
| T_DX_0 | >f8 |  | 0.006380328422086341 | `coords['T_DX_0']` (per-fiber table) |
| T_DY_0 | >f8 |  | -0.013355827626028053 | `coords['T_DY_0']` (per-fiber table) |
| F_DX_0 | >f8 |  | 0.007 | `coords['F_DX_0']` (per-fiber table) |
| F_DY_0 | >f8 |  | -0.01 | `coords['F_DY_0']` (per-fiber table) |
| FPA_X_0 | >f8 |  | 41.000619671577915 | `coords['FPA_X_0']` (per-fiber table) |
| FPA_Y_0 | >f8 |  | 79.17035582762603 | `coords['FPA_Y_0']` (per-fiber table) |
| T_FPA_X_0 | >f8 |  | 41.000619671577915 | `coords['T_FPA_X_0']` (per-fiber table) |
| T_FPA_Y_0 | >f8 |  | 79.17035582762603 | `coords['T_FPA_Y_0']` (per-fiber table) |
| F_FPA_X_0 | >f8 |  | 41.0 | `coords['F_FPA_X_0']` (per-fiber table) |
| F_FPA_Y_0 | >f8 |  | 79.167 | `coords['F_FPA_Y_0']` (per-fiber table) |
| TURB_X_0 | >f8 |  | -0.0006196715779136592 | `coords['TURB_X_0']` (per-fiber table) |
| TURB_Y_0 | >f8 |  | -0.0033558276260280528 | `coords['TURB_Y_0']` (per-fiber table) |
| FLAGS_COR_0 | >i8 |  | 16842821 | `coords['FLAGS_COR_0']` (per-fiber table) |
| REQ_X_0 | >f8 |  | 41.007000000000005 | `coords['REQ_X_0']` (per-fiber table) |
| REQ_Y_0 | >f8 |  | 79.157 | `coords['REQ_Y_0']` (per-fiber table) |
| OFFSET_0 | >f8 |  | 0.014801578373601139 | `coords['OFFSET_0']` (per-fiber table) |
| HACK_X_0 | >f8 |  | 41.003 | `coords['HACK_X_0']` (per-fiber table) |
| HACK_Y_0 | >f8 |  | 79.178 | `coords['HACK_Y_0']` (per-fiber table) |
| EXP_Q_1 | >f8 |  | 62.6078714537288 | `coords['EXP_Q_1']` (per-fiber table) |
| EXP_S_1 | >f8 |  | 89.16406750003033 | `coords['EXP_S_1']` (per-fiber table) |
| FLAGS_EXP_1 | >i8 |  | 16842756 | `coords['FLAGS_EXP_1']` (per-fiber table) |
| EXP_X_1 | >f8 |  | 41.020101682497774 | `coords['EXP_X_1']` (per-fiber table) |
| EXP_Y_1 | >f8 |  | 79.16241488372437 | `coords['EXP_Y_1']` (per-fiber table) |
| FVC_X_1 | >f8 |  | -288.614 | `coords['FVC_X_1']` (per-fiber table) |
| FVC_Y_1 | >f8 |  | 554.914 | `coords['FVC_Y_1']` (per-fiber table) |
| FLAGS_FVC_1 | >i8 |  | 16842756 | `coords['FLAGS_FVC_1']` (per-fiber table) |
| CNT_X_1 | >f8 |  | -286.6489999999999 | `coords['CNT_X_1']` (per-fiber table) |
| CNT_Y_1 | >f8 |  | 551.4580000000001 | `coords['CNT_Y_1']` (per-fiber table) |
| FLAGS_CNT_1 | >i8 |  | 16842821 | `coords['FLAGS_CNT_1']` (per-fiber table) |
| CNT_MAG_1 | >f8 |  | 13.441 | `coords['CNT_MAG_1']` (per-fiber table) |
| CNT_ERR_1 | >f8 |  | 0.001 | `coords['CNT_ERR_1']` (per-fiber table) |
| DX_1 | >f8 |  | 0.003635900698307432 | `coords['DX_1']` (per-fiber table) |
| DY_1 | >f8 |  | -0.014734424551726643 | `coords['DY_1']` (per-fiber table) |
| T_DX_1 | >f8 |  | 0.003635900698307432 | `coords['T_DX_1']` (per-fiber table) |
| T_DY_1 | >f8 |  | -0.014734424551726643 | `coords['T_DY_1']` (per-fiber table) |
| F_DX_1 | >f8 |  | 0.014 | `coords['F_DX_1']` (per-fiber table) |
| F_DY_1 | >f8 |  | -0.02 | `coords['F_DY_1']` (per-fiber table) |
| FPA_X_1 | >f8 |  | 41.00836409930169 | `coords['FPA_X_1']` (per-fiber table) |
| FPA_Y_1 | >f8 |  | 79.16873442455173 | `coords['FPA_Y_1']` (per-fiber table) |
| T_FPA_X_1 | >f8 |  | 41.00836409930169 | `coords['T_FPA_X_1']` (per-fiber table) |
| T_FPA_Y_1 | >f8 |  | 79.16873442455173 | `coords['T_FPA_Y_1']` (per-fiber table) |
| F_FPA_X_1 | >f8 |  | 40.998 | `coords['F_FPA_X_1']` (per-fiber table) |
| F_FPA_Y_1 | >f8 |  | 79.174 | `coords['F_FPA_Y_1']` (per-fiber table) |
| TURB_X_1 | >f8 |  | -0.010364099301692568 | `coords['TURB_X_1']` (per-fiber table) |
| TURB_Y_1 | >f8 |  | 0.0052655754482733574 | `coords['TURB_Y_1']` (per-fiber table) |
| FLAGS_COR_1 | >i8 |  | 16842821 | `coords['FLAGS_COR_1']` (per-fiber table) |
| REQ_X_1 | >f8 |  | 41.01199999999999 | `coords['REQ_X_1']` (per-fiber table) |
| REQ_Y_1 | >f8 |  | 79.154 | `coords['REQ_Y_1']` (per-fiber table) |
| OFFSET_1 | >f8 |  | 0.015176397489472835 | `coords['OFFSET_1']` (per-fiber table) |
| HACK_X_1 | >f8 |  | 40.993 | `coords['HACK_X_1']` (per-fiber table) |
| HACK_Y_1 | >f8 |  | 79.187 | `coords['HACK_Y_1']` (per-fiber table) |
| FIBER_RA | >f8 | Fiber pointing RA (deg) | 215.95044673663642 | `coords['FIBER_RA']` (per-fiber table) |
| FIBER_DEC | >f8 | Fiber pointing Dec (deg) | -8.680311208436967 | `coords['FIBER_DEC']` (per-fiber table) |
| FIBER_X | >f8 | Fiber X (post-correction) | 41.00836409930169 | `coords['FIBER_X']` (per-fiber table) |
| FIBER_Y | >f8 | Fiber Y (post-correction) | 79.16873442455173 | `coords['FIBER_Y']` (per-fiber table) |
| FIBER_DX | >f4 |  | 0.0036359008 | `coords['FIBER_DX']` (per-fiber table) |
| FIBER_DY | >f4 |  | -0.014734425 | `coords['FIBER_DY']` (per-fiber table) |
| FIBER_OFFSET | >f4 |  | 0.015176398 | `coords['FIBER_OFFSET']` (per-fiber table) |


## Exposure directory: `etc-<expid>.json` -- `header` block (scalar ETC summary)

Full file also has expinfo/fassign/acquisition/guide_stars blocks (nested, exposure-setup info) and shutter/thru/sky/accum time-series blocks (parallel lists, one entry per ETC update) -- not flattened here; see `Exposure.etc`/`etc_timeseries(key)`.

| Field | Type | Description | Example value | Source |
|---|---|---|---|---|
| ACQFWHM | float | Acquisition-image FWHM (seeing proxy) | 2.279347 | `etc_summary['ACQFWHM']` |
| ETCFRACB | float |  | 0.134257 | `etc_summary['ETCFRACB']` |
| ETCFRACE | float |  | 0.295558 | `etc_summary['ETCFRACE']` |
| ETCFRACP | float |  | 0.380492 | `etc_summary['ETCFRACP']` |
| ETCPREV | float |  | 0.0 | `etc_summary['ETCPREV']` |
| ETCPROF | str | ETC target-brightness profile used (e.g. BGS, ELG) | BGS | `etc_summary['ETCPROF']` |
| ETCREAL | float | ETC real (elapsed shutter-open) time (s) | 1068.442993 | `etc_summary['ETCREAL']` |
| ETCSKY | float | ETC-estimated sky brightness | 1.973706 | `etc_summary['ETCSKY']` |
| ETCSPLIT | int | Number of cosmic-ray splits ETC has triggered so far | 1 | `etc_summary['ETCSPLIT']` |
| ETCTEFF | float | ETC-estimated effective exposure time (s) at the time reported | 182.517883 | `etc_summary['ETCTEFF']` |
| ETCTHRUB | float |  | 0.581015 | `etc_summary['ETCTHRUB']` |
| ETCTHRUE | float |  | 0.589107 | `etc_summary['ETCTHRUE']` |
| ETCTHRUP | float |  | 0.556269 | `etc_summary['ETCTHRUP']` |
| ETCTRANS | float | ETC-estimated atmospheric transparency | 0.821598 | `etc_summary['ETCTRANS']` |
| ETCVERS | str |  | 0.1.21 | `etc_summary['ETCVERS']` |


## Exposure directory: `centroids-<expid>.json`

Not a flat table -- top-level scalar fields (`expid`, `status`, `started_at`/`ended_at`, `target_ra`/`target_dec`, `mount_ha`/`mount_dec`), a `summary` dict (whole-exposure guiding stats: `duration`, `seeing`, `frames`, `meanx`/`meany`/etc.), and a `frames` dict keyed by frame number (1-indexed as *strings*) -- each frame's content is the file-based counterpart of one `telemetry.guider_centroids` row (same fields: `combined_x`/`combined_y`/`seeing`/`nstars`/`ngfas`/`tcs_correction_ra`/`tcs_correction_dec`/`guiding`, plus per-GFA-camera `GUIDE{n}_{0,1}` sub-blocks). `Exposure.centroids` returns this whole structure as-is (not parsed further); `Exposure.guider_centroids` (DB) is the preferred, already-structured equivalent.


## Offline QA: `exposures-daily.csv`

Live example row: expid 359483. Full schema, one row per (science) exposure.

| Field | Type | Description | Example value | Source |
|---|---|---|---|---|
| NIGHT | int64 | Observing night (YYYYMMDD) | 20260702 | `redux_row['NIGHT']` |
| EXPID | int64 | Exposure ID | 359483 | `redux_row['EXPID']` |
| TILEID | int64 | Tile ID observed | 31562 | `redux_row['TILEID']` |
| TILERA | float64 |  | 216.12 | `redux_row['TILERA']` |
| TILEDEC | float64 |  | -9.006 | `redux_row['TILEDEC']` |
| MJD | float64 |  | 61224.17344401 | `redux_row['MJD']` |
| SURVEY | str |  | main | `redux_row['SURVEY']` |
| PROGRAM | str | Survey program (dark/bright/backup/other) | bright | `redux_row['PROGRAM']` |
| FAPRGRM | str |  | bright | `redux_row['FAPRGRM']` |
| FAFLAVOR | str |  | mainbright | `redux_row['FAFLAVOR']` |
| EXPTIME | float64 | Requested exposure time (s) | 1065.1 | `redux_row['EXPTIME']` |
| EFFTIME_SPEC | float64 | Pipeline-measured effective spectroscopic time (s) -- what exposure_table/exposure-qa's EFFTIME should closely match | 229.8 | `redux_row['EFFTIME_SPEC']` |
| GOALTIME | float64 |  | 180.0 | `redux_row['GOALTIME']` |
| GOALTYPE | str |  | bright | `redux_row['GOALTYPE']` |
| MINTFRAC | float64 |  | 0.85 | `redux_row['MINTFRAC']` |
| AIRMASS | float64 |  | 1.382 | `redux_row['AIRMASS']` |
| EBV | float64 |  | 0.062 | `redux_row['EBV']` |
| SEEING_ETC | float64 |  | 2.279 | `redux_row['SEEING_ETC']` |
| EFFTIME_ETC | float64 |  | 182.5 | `redux_row['EFFTIME_ETC']` |
| TSNR2_ELG | float64 | Per-exposure total (summed across petals/arms) ELG template S/N^2 -- same metric as PETALQA's TSNR2_ELG_{B,R,Z} but pre-aggregated | 26.1 | `redux_row['TSNR2_ELG']` |
| TSNR2_QSO | float64 | Per-exposure total QSO template S/N^2 | 5.5 | `redux_row['TSNR2_QSO']` |
| TSNR2_LRG | float64 | Per-exposure total LRG template S/N^2 | 18.3 | `redux_row['TSNR2_LRG']` |
| TSNR2_LYA | float64 | Per-exposure total LYA template S/N^2 | 14.0 | `redux_row['TSNR2_LYA']` |
| TSNR2_BGS | float64 | Per-exposure total BGS template S/N^2 | 1641.5 | `redux_row['TSNR2_BGS']` |
| TSNR2_GPBDARK | float64 |  | 2542.3 | `redux_row['TSNR2_GPBDARK']` |
| TSNR2_GPBBRIGHT | float64 |  | 492.9 | `redux_row['TSNR2_GPBBRIGHT']` |
| TSNR2_GPBBACKUP | float64 |  | 3889.7 | `redux_row['TSNR2_GPBBACKUP']` |
| LRG_EFFTIME_DARK | float64 |  | 222.3 | `redux_row['LRG_EFFTIME_DARK']` |
| ELG_EFFTIME_DARK | float64 |  | 224.5 | `redux_row['ELG_EFFTIME_DARK']` |
| BGS_EFFTIME_BRIGHT | float64 |  | 229.8 | `redux_row['BGS_EFFTIME_BRIGHT']` |
| LYA_EFFTIME_DARK | float64 |  | 165.4 | `redux_row['LYA_EFFTIME_DARK']` |
| GPB_EFFTIME_DARK | float64 |  | 213.1 | `redux_row['GPB_EFFTIME_DARK']` |
| GPB_EFFTIME_BRIGHT | float64 |  | 257.9 | `redux_row['GPB_EFFTIME_BRIGHT']` |
| GPB_EFFTIME_BACKUP | float64 |  | 275.5 | `redux_row['GPB_EFFTIME_BACKUP']` |
| TRANSPARENCY_GFA | float64 |  | 0.947 | `redux_row['TRANSPARENCY_GFA']` |
| SEEING_GFA | float64 | Seeing from (older/different) GFA analysis -- compare to gfa_row['FWHM_ASEC'] from the newer offline GFA pipeline | 1.518 | `redux_row['SEEING_GFA']` |
| FIBER_FRACFLUX_GFA | float64 |  | 0.37 | `redux_row['FIBER_FRACFLUX_GFA']` |
| FIBER_FRACFLUX_ELG_GFA | float64 |  | 0.287 | `redux_row['FIBER_FRACFLUX_ELG_GFA']` |
| FIBER_FRACFLUX_BGS_GFA | float64 |  | 0.138 | `redux_row['FIBER_FRACFLUX_BGS_GFA']` |
| FIBERFAC_GFA | float64 |  | 0.559 | `redux_row['FIBERFAC_GFA']` |
| FIBERFAC_ELG_GFA | float64 |  | 0.595 | `redux_row['FIBERFAC_ELG_GFA']` |
| FIBERFAC_BGS_GFA | float64 |  | 0.624 | `redux_row['FIBERFAC_BGS_GFA']` |
| AIRMASS_GFA | float64 | Airmass from GFA analysis | 1.402 | `redux_row['AIRMASS_GFA']` |
| SKY_MAG_AB_GFA | float64 |  | 20.767 | `redux_row['SKY_MAG_AB_GFA']` |
| SKY_MAG_G_SPEC | float64 |  | 21.554 | `redux_row['SKY_MAG_G_SPEC']` |
| SKY_MAG_R_SPEC | float64 |  | 20.844 | `redux_row['SKY_MAG_R_SPEC']` |
| SKY_MAG_Z_SPEC | float64 |  | 19.012 | `redux_row['SKY_MAG_Z_SPEC']` |
| EFFTIME_GFA | float64 |  | 261.1 | `redux_row['EFFTIME_GFA']` |
| EFFTIME_DARK_GFA | float64 |  | 231.0 | `redux_row['EFFTIME_DARK_GFA']` |
| EFFTIME_BRIGHT_GFA | float64 |  | 261.1 | `redux_row['EFFTIME_BRIGHT_GFA']` |
| EFFTIME_BACKUP_GFA | float64 |  | 283.6 | `redux_row['EFFTIME_BACKUP_GFA']` |


## Offline QA: `exposure_table_<night>.csv`

One row per exposure that night, including calibration frames. Field definitions from `desispec.workflow.exptable` (installed pipeline source), not just docstrings. The module surfaces a curated 6-field subset via `exp.exposure_table_flags` (`LASTSTEP`, `CAMWORD`, `BADCAMWORD`, `BADAMPS`, `EXPFLAG`, `HEADERERR`); every other column (shown as `—`) comes from `telemetry_mining.redux.exposure_table_row(expid, night, config)`.

| Field | Type | Description | Example value | Source |
|---|---|---|---|---|
| EXPID | int64 |  | 359483 | — |
| OBSTYPE | str | Observation type incl. calibration frames: zero, dark, arc, flat, science (not present in exposures-daily.csv, which is science-only) | science | — |
| TILEID | int64 |  | 31562 | — |
| LASTSTEP | str | Closed vocabulary (desispec.workflow.exptable.get_last_step_options): ignore, skysub, stdstarfit, fluxcal, all -- how far the pipeline processed this exposure | all | `exposure_table_flags['LASTSTEP']` |
| CAMWORD | str | Which cameras exist, compact 'a'+spectrograph-number encoding (desispec.io.util.create_camword) | a0123456789 | `exposure_table_flags['CAMWORD']` |
| BADCAMWORD | float64 | Same encoding, cameras excluded from processing | nan | `exposure_table_flags['BADCAMWORD']` |
| BADAMPS | float64 | Comma-separated '{camera}{petal}{amp}' entries, e.g. 'b7D,z8A' (desispec.io.util.parse_badamps) | nan | `exposure_table_flags['BADAMPS']` |
| EXPTIME | float64 |  | 1065.056 | — |
| EFFTIME_ETC | float64 |  | 182.517883 | — |
| SURVEY | str |  | main | — |
| FA_SURV | str |  | main | — |
| FAPRGRM | str |  | bright | — |
| GOALTIME | float64 |  | 180.0 | — |
| GOALTYPE | str |  | bright | — |
| EBVFAC | float64 |  | 1.1170389013777 | — |
| AIRMASS | float64 |  | 1.382467 | — |
| SPEED | float64 |  | 0.3768907064783952 | — |
| TARGTRA | float64 |  | 216.11585 | — |
| TARGTDEC | float64 |  | -9.0164 | — |
| SEQNUM | int64 |  | 1 | — |
| SEQTOT | int64 |  | 1 | — |
| PROGRAM | str |  | backup | — |
| PURPOSE | str |  | main survey | — |
| MJD-OBS | float64 |  | 61224.173444018 | — |
| NIGHT | int64 |  | 20260702 | — |
| HEADERERR | str | 'key:->value' metadata corrections applied to this exposure's row, e.g. 'SEQTOT:->1' | \| | `exposure_table_flags['HEADERERR']` |
| EXPFLAG | str | Closed vocabulary (get_exposure_flags): good, extra_cal, low_flux, short_exposure, low_sn, low_speed, aborted, metadata_missing, metadata_mismatch, misconfig_cal, misconfig_petal, off_target, no_stdstars, test, corrupted, junk, bad | \| | `exposure_table_flags['EXPFLAG']` |
| COMMENTS | str | Free-form human notes -- confirmed NOT used by the pipeline itself, deliberately excluded from Exposure.exposure_table_flags | \| | — |


## Offline QA: `tiles-daily.csv`

One row per tile, **indexed by `TILEID` (not `EXPID`)**. Not surfaced by `Exposure` -- read `Config.redux_daily_dir/'tiles-daily.csv'` directly, or attach a custom `TableSource(index_column='TILEID')`. (Low priority -- see project memory.)

| Field | Type | Description | Example value | Source |
|---|---|---|---|---|
| TILEID | int64 |  | 70004 | — |
| SURVEY | str |  | cmx | — |
| PROGRAM | str |  | other | — |
| FAPRGRM | str |  | unknown | — |
| FAFLAVOR | str |  | unknown | — |
| NEXP | int64 |  | 4 | — |
| EXPTIME | float64 |  | 3600.0 | — |
| TILERA | float64 |  | 116.0 | — |
| TILEDEC | float64 |  | 20.7 | — |
| EFFTIME_ETC | float64 |  | 0.0 | — |
| EFFTIME_SPEC | float64 |  | 3619.8 | — |
| EFFTIME_GFA | float64 |  | 0.0 | — |
| GOALTIME | float64 |  | 1000.0 | — |
| OBSSTATUS | str |  | obsend | — |
| LRG_EFFTIME_DARK | float64 |  | 3470.8 | — |
| ELG_EFFTIME_DARK | float64 |  | 3619.8 | — |
| BGS_EFFTIME_BRIGHT | float64 |  | 3784.0 | — |
| LYA_EFFTIME_DARK | float64 |  | 3056.6 | — |
| GOALTYPE | str |  | other | — |
| MINTFRAC | float64 |  | 0.9 | — |
| LASTNIGHT | int64 |  | 20200219 | — |
| UPDATED | str |  | 2025-03-18T01:39:39-0700 | — |


## Database: `exposure.exposure`

187 columns, one row per exposure. Live example: expid 359483. Only columns with a known/discussed meaning have a description -- the rest are listed for completeness with a real example value.

| Field | Type | Description | Example value | Source |
|---|---|---|---|---|
| id | integer | Exposure ID (primary key) | 359483 | `db_row['id']` |
| data_location | text |  | /exposures/desi/20260702/00359483/desi-00359483.fits | `db_row['data_location']` |
| thumbnail | text |  | exposures/desi/png/focus/20260702/00359483 | `db_row['thumbnail']` |
| errors | text |  | None | `db_row['errors']` |
| targtra | double precision |  | 216.11585 | `db_row['targtra']` |
| targtdec | double precision |  | -9.0164 | `db_row['targtdec']` |
| telstat | text |  | None | `db_row['telstat']` |
| skyra | double precision | Sky-pointing RA | 216.11585 | `db_row['skyra']` |
| skydec | double precision | Sky-pointing Dec | -9.0164 | `db_row['skydec']` |
| reqra | double precision |  | 216.12 | `db_row['reqra']` |
| reqdec | double precision |  | -9.006 | `db_row['reqdec']` |
| deltara | double precision |  | None | `db_row['deltara']` |
| deltadec | double precision |  | None | `db_row['deltadec']` |
| reqtime | double precision |  | 1860.0 | `db_row['reqtime']` |
| exptime | double precision | Requested exposure time (s) | 1065.056 | `db_row['exptime']` |
| flavor | text |  | science | `db_row['flavor']` |
| program | text | Survey program | BACKUP | `db_row['program']` |
| lead | text |  | Luke Tyas | `db_row['lead']` |
| propid | text |  | 2020B-5000 | `db_row['propid']` |
| object | text |  |  | `db_row['object']` |
| instance | text |  | desi_20260702 | `db_row['instance']` |
| utc_dark | double precision |  | None | `db_row['utc_dark']` |
| utc_beg | double precision |  | None | `db_row['utc_beg']` |
| utc_end | double precision |  | None | `db_row['utc_end']` |
| positioned | boolean |  | True | `db_row['positioned']` |
| prepared | boolean |  | True | `db_row['prepared']` |
| started | boolean |  | True | `db_row['started']` |
| exposed | boolean |  | True | `db_row['exposed']` |
| digitized | boolean |  | True | `db_row['digitized']` |
| built | boolean |  | True | `db_row['built']` |
| distributed | boolean |  | True | `db_row['distributed']` |
| paused | boolean |  | False | `db_row['paused']` |
| aborted | boolean |  | False | `db_row['aborted']` |
| saved | boolean |  | True | `db_row['saved']` |
| saved_updated | timestamp with time zone |  | None | `db_row['saved_updated']` |
| discard | boolean |  | False | `db_row['discard']` |
| aos | boolean |  | False | `db_row['aos']` |
| seeing | double precision | Seeing estimate (source/timing vs. pmseeing/etcseeing not fully disambiguated) | 2.2975 | `db_row['seeing']` |
| focus | ARRAY |  | [1347.3, -187.7, -1309.6, -18.4, 32.3, -32.8] | `db_row['focus']` |
| tileid | integer | Tile ID | 31562 | `db_row['tileid']` |
| inposition | double precision |  | None | `db_row['inposition']` |
| positer | integer |  | None | `db_row['positer']` |
| ntargets | integer |  | None | `db_row['ntargets']` |
| seqid | text |  | None | `db_row['seqid']` |
| seqnum | integer |  | 1 | `db_row['seqnum']` |
| seqtot | integer |  | None | `db_row['seqtot']` |
| moonangl | double precision |  | None | `db_row['moonangl']` |
| airmass | double precision | Airmass | 1.382467 | `db_row['airmass']` |
| mountha | double precision | Mount hour angle. Confirmed to sometimes differ from `db_row['tcs']['mount_ha']` for the same exposure (e.g. 0.204 vs. 0.383) -- distinct measurement snapshots, not interchangeable. | 15.759805 | `db_row['mountha']` |
| zd | double precision |  | 43.719253 | `db_row['zd']` |
| mountaz | double precision | Mount azimuth | 202.864377 | `db_row['mountaz']` |
| domeaz | double precision |  | 208.448 | `db_row['domeaz']` |
| st | text |  | 15:28:11.371000 | `db_row['st']` |
| raoffset | double precision |  | None | `db_row['raoffset']` |
| decoffset | double precision |  | None | `db_row['decoffset']` |
| slewangl | double precision |  | 41.921 | `db_row['slewangl']` |
| readout_time | double precision |  | None | `db_row['readout_time']` |
| hexapod_time | double precision |  | None | `db_row['hexapod_time']` |
| slew_time | double precision |  | None | `db_row['slew_time']` |
| time_between_exposures | double precision |  | None | `db_row['time_between_exposures']` |
| script | text |  | None | `db_row['script']` |
| manifest | text |  | false | `db_row['manifest']` |
| spectrographs | ARRAY |  | ['SP0', 'SP1', 'SP2', 'SP3', 'SP4', 'SP5', 'SP6', 'SP7', ... | `db_row['spectrographs']` |
| update_time | timestamp with time zone |  | 2026-07-03 04:29:53.078233+00:00 | `db_row['update_time']` |
| frames | integer |  | 0 | `db_row['frames']` |
| multiframe | boolean |  | False | `db_row['multiframe']` |
| reqha | double precision |  | None | `db_row['reqha']` |
| reqaz | double precision |  | None | `db_row['reqaz']` |
| reqel | double precision |  | None | `db_row['reqel']` |
| image_cameras | ARRAY |  | None | `db_row['image_cameras']` |
| guide_cameras | ARRAY |  | ['GUIDE0', 'GUIDE2', 'GUIDE3', 'GUIDE5', 'GUIDE7', 'GUIDE8'] | `db_row['guide_cameras']` |
| focus_cameras | ARRAY |  | ['FOCUS1', 'FOCUS4', 'FOCUS6', 'FOCUS9'] | `db_row['focus_cameras']` |
| excluded | ARRAY |  | [] | `db_row['excluded']` |
| fiberassign | text |  | None | `db_row['fiberassign']` |
| s2n | double precision |  | None | `db_row['s2n']` |
| transpar | double precision |  | None | `db_row['transpar']` |
| skylevel | double precision |  | 1.88 | `db_row['skylevel']` |
| zenith | boolean |  | False | `db_row['zenith']` |
| dominpos | boolean |  | True | `db_row['dominpos']` |
| whitespt | boolean |  | False | `db_row['whitespt']` |
| inpos | boolean |  | True | `db_row['inpos']` |
| inctrl | boolean |  | True | `db_row['inctrl']` |
| mjd_obs | double precision |  | 61224.173444018 | `db_row['mjd_obs']` |
| date_obs | timestamp with time zone | Shutter-open timestamp (timestamptz) -- primary source for Exposure.time_window | 2026-07-03 04:09:45.563203+00:00 | `db_row['date_obs']` |
| moonra | double precision |  | 318.954513 | `db_row['moonra']` |
| moondec | double precision |  | -17.212429 | `db_row['moondec']` |
| guider_mode | text |  | catalog | `db_row['guider_mode']` |
| collected | boolean |  | True | `db_row['collected']` |
| night | integer | Observing night | 20260702 | `db_row['night']` |
| ups | jsonb |  | {'npos': 1.0, 'status': 'System Normal - On Line(7)', 'OU... | `db_row['ups']` |
| dome | jsonb |  | {'B29fan': 'off', 'C_floor': 19.8, 'SCR_roof': 20.8, 'pla... | `db_row['dome']` |
| computer | jsonb |  | {'COMPDEW': -2.9, 'COMPHUM': 16.5, 'glycol_in': 4.8, 'amb... | `db_row['computer']` |
| telescope | jsonb |  | {'air_flow': 0.0, 'air_temp': 20.262, 'wind_gust': 0, 'tr... | `db_row['telescope']` |
| tower | jsonb |  | {'dimm': 0.0, 'gust': 11.8, 'split': 32.6, 'dewpoint': -1... | `db_row['tower']` |
| parallactic | double precision |  | 19.698296 | `db_row['parallactic']` |
| tcsmjd | double precision |  | 61224.173889 | `db_row['tcsmjd']` |
| pmready | boolean |  | None | `db_row['pmready']` |
| mntoffd | double precision |  | None | `db_row['mntoffd']` |
| mntoffr | double precision |  | None | `db_row['mntoffr']` |
| se_annex | boolean |  | False | `db_row['se_annex']` |
| guidoffr | double precision |  | None | `db_row['guidoffr']` |
| guidoffd | double precision |  | None | `db_row['guidoffd']` |
| petals | ARRAY |  | ['PETAL0', 'PETAL1', 'PETAL2', 'PETAL3', 'PETAL4', 'PETAL... | `db_row['petals']` |
| cal_lamps | ARRAY |  | None | `db_row['cal_lamps']` |
| skytime | double precision |  | 60.0 | `db_row['skytime']` |
| focstime | double precision |  | 60.0 | `db_row['focstime']` |
| guidtime | double precision |  | 5.0 | `db_row['guidtime']` |
| mountel | double precision | Mount elevation | 46.339571 | `db_row['mountel']` |
| hexapod | jsonb |  | {'hex_trim': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], 'rot_rate': ... | `db_row['hexapod']` |
| adc | jsonb |  | {'status': 'SUCCESS', 'adc_home1': False, 'adc_home2': Fa... | `db_row['adc']` |
| action | text |  | None | `db_row['action']` |
| sequence | text | Exposure sequence type (e.g. DESI) | DESI | `db_row['sequence']` |
| observers | ARRAY |  | None | `db_row['observers']` |
| exposing | boolean |  | False | `db_row['exposing']` |
| done | boolean |  | True | `db_row['done']` |
| digitizing | boolean |  | False | `db_row['digitizing']` |
| obstype | text | Observation type | SCIENCE | `db_row['obstype']` |
| request | jsonb |  | {'ID': 52, 'GFA': 'DESIROOT/target/catalogs/dr9/1.1.1/gfa... | `db_row['request']` |
| callamps | jsonb |  | None | `db_row['callamps']` |
| vccd | text |  | ON | `db_row['vccd']` |
| ondeck | boolean |  | True | `db_row['ondeck']` |
| split | boolean |  | None | `db_row['split']` |
| positioning | boolean |  | False | `db_row['positioning']` |
| purpose | text |  | Main Survey | `db_row['purpose']` |
| vccd_on_since | timestamp with time zone |  | None | `db_row['vccd_on_since']` |
| fvctime | double precision |  | None | `db_row['fvctime']` |
| acqtime | double precision |  | 15.0 | `db_row['acqtime']` |
| acqusition_cameras | ARRAY |  | None | `db_row['acqusition_cameras']` |
| reqteff | double precision | Requested effective time (s) | 180.0 | `db_row['reqteff']` |
| etc | jsonb | jsonb block: ETC summary for this exposure | {'expid': 359483, 'sbprof': 'BGS', 'seeing': 2.2793, 'tra... | `db_row['etc']` |
| ntssurvey | text |  | main | `db_row['ntssurvey']` |
| ntsprog | text |  | BRIGHT | `db_row['ntsprog']` |
| esttime | double precision |  | 2056.11 | `db_row['esttime']` |
| totteff | double precision | Total accumulated effective time (ETC real-time estimate) -- confirmed distinct from redux_row['EFFTIME_SPEC'] (post-hoc pipeline measurement), different values for the same exposure | 182.0525 | `db_row['totteff']` |
| pmseeing | double precision | Platemaker-measured seeing | 2.2975 | `db_row['pmseeing']` |
| etctrans | double precision |  | 0.821598 | `db_row['etctrans']` |
| etcseeing | double precision | ETC-measured seeing | 2.2793 | `db_row['etcseeing']` |
| maxtime | double precision |  | 5400.0 | `db_row['maxtime']` |
| etcteff | double precision |  | 182.517883 | `db_row['etcteff']` |
| etcreal | double precision |  | 1068.442993 | `db_row['etcreal']` |
| etcprev | double precision |  | 0.0 | `db_row['etcprev']` |
| etcsplit | integer |  | 1 | `db_row['etcsplit']` |
| etcprof | text |  | BGS | `db_row['etcprof']` |
| etcthrup | double precision |  | 0.556269 | `db_row['etcthrup']` |
| etcthrue | double precision |  | 0.589107 | `db_row['etcthrue']` |
| etcthrub | double precision |  | 0.581015 | `db_row['etcthrub']` |
| etcfracp | double precision |  | 0.380492 | `db_row['etcfracp']` |
| etcfrace | double precision |  | 0.295558 | `db_row['etcfrace']` |
| etcfracb | double precision |  | 0.134257 | `db_row['etcfracb']` |
| etcsky | double precision |  | 1.973706 | `db_row['etcsky']` |
| acqfwhm | double precision |  | 2.279347 | `db_row['acqfwhm']` |
| pmtransparency | double precision |  | None | `db_row['pmtransparency']` |
| etctransparency | double precision |  | None | `db_row['etctransparency']` |
| moonsep | double precision |  | 100.429 | `db_row['moonsep']` |
| slewtime | double precision |  | 112.782 | `db_row['slewtime']` |
| startadj | timestamp without time zone |  | 2026-07-03 04:06:16.324266 | `db_row['startadj']` |
| openshut | timestamp without time zone |  | 2026-07-03 04:09:46.164148 | `db_row['openshut']` |
| poscycle | integer |  | 1 | `db_row['poscycle']` |
| poscnvgd | integer |  | 604 | `db_row['poscnvgd']` |
| posenabl | integer |  | 4340 | `db_row['posenabl']` |
| posdosab | integer |  | None | `db_row['posdosab']` |
| posrms | double precision | Fiber positioner RMS (real-time telemetry) -- confirmed distinct from fiberqa['FPRMS2D'] (post-hoc QA), different values for the same exposure | 0.0042 | `db_row['posrms']` |
| turbrms | double precision | Turbulence RMS component of positioning | 0.0085 | `db_row['turbrms']` |
| posonfrc | double precision |  | 0.9774 | `db_row['posonfrc']` |
| poscvfrc | double precision |  | 0.1392 | `db_row['poscvfrc']` |
| posontgt | integer |  | 4242 | `db_row['posontgt']` |
| last_onfraction | double precision |  | None | `db_row['last_onfraction']` |
| tcs | jsonb | jsonb block: telescope control system state | {'zd': 43.719253, 'tcsst': '15:28:12.774', 'fvc_ha': 15.8... | `db_row['tcs']` |
| gfatime | double precision |  | None | `db_row['gfatime']` |
| mintime | double precision |  | None | `db_row['mintime']` |
| domshutu | boolean |  | None | `db_row['domshutu']` |
| domshutl | boolean |  | None | `db_row['domshutl']` |
| domlighl | boolean |  | None | `db_row['domlighl']` |
| domlighh | boolean |  | None | `db_row['domlighh']` |
| pmcover | boolean |  | None | `db_row['pmcover']` |
| pmcool | boolean |  | None | `db_row['pmcool']` |
| useturb | boolean |  | None | `db_row['useturb']` |
| rotenbld | boolean |  | None | `db_row['rotenbld']` |
| rotrate | double precision | **Confirmed dead: only 1 non-null value across the entire exposure.exposure table's full history (2019-2026)** -- a known bug in the online ingestion code, not yet fixed. Use `db_row['hexapod']['rot_rate']` instead (same physical quantity, different key name -- confirmed matching the FITS header's ROTRATE for a spot-checked exposure); not universal either, since `hexapod` isn't populated for every exposure sequence. | None | `db_row['rotrate']` |
| rotoffst | double precision | **Confirmed dead: 0 non-null values across the entire exposure.exposure table.** No known populated DB-resident substitute -- use `header.ROTOFFST` (requires opening the FITS file). | None | `db_row['rotoffst']` |
| winddir | double precision | Wind direction -- often None/unpopulated even when the FITS header has a value; prefer header for this field | None | `db_row['winddir']` |
| windspd | double precision | Wind speed -- same caveat as winddir | None | `db_row['windspd']` |
| gust | double precision | Wind gust -- same caveat | None | `db_row['gust']` |
| pmirtemp | double precision | Primary mirror temperature -- same caveat, often None in DB row even when header has it | None | `db_row['pmirtemp']` |
| seqstart | timestamp with time zone |  | 2026-07-03 04:06:02.969682+00:00 | `db_row['seqstart']` |
| astrometry | jsonb |  | {'expid': 359483, 'astro_fwhm': 2.3, 'astro_rmsx': 0.055,... | `db_row['astrometry']` |
| guider | jsonb | jsonb block: guider-related summary for this exposure | {'maxx': 0.814, 'maxy': 0.5, 'meanx': 0.319, 'meany': 0.0... | `db_row['guider']` |


## Database: `exposure.stars`

| Field | Type | Description | Example value | Source |
|---|---|---|---|---|
| star_id | integer |  |  | `stars['star_id']` (per-star table) |
| expid | integer |  |  | `stars['expid']` (per-star table) |
| ra | double precision |  |  | `stars['ra']` (per-star table) |
| dec | double precision |  |  | `stars['dec']` (per-star table) |
| mag | double precision |  |  | `stars['mag']` (per-star table) |
| gfaid | integer |  |  | `stars['gfaid']` (per-star table) |
| objtype | text |  |  | `stars['objtype']` (per-star table) |
| okguide | boolean |  |  | `stars['okguide']` (per-star table) |


## Database: `exposure.comments`

| Field | Type | Description | Example value | Source |
|---|---|---|---|---|
| id | integer |  |  | `comments['id']` (per-comment table) |
| exposure_id | integer |  |  | `comments['exposure_id']` (per-comment table) |
| date | timestamp with time zone |  |  | `comments['date']` (per-comment table) |
| comment_text | text |  |  | `comments['comment_text']` (per-comment table) |


## Database: `exposure.positions`

Not surfaced by an `Exposure` accessor -- query `exposure.positions` directly via `telemetry_mining.db.fetch_df`, or add a custom `TableSource`. (Source `—` throughout.)

| Field | Type | Description | Example value | Source |
|---|---|---|---|---|
| position_id | integer |  |  | — |
| expid | integer |  |  | — |
| iteration | integer |  |  | — |
| pid | integer |  |  | — |
| type | text |  |  | — |
| format | text |  |  | — |
| x | double precision |  |  | — |
| y | double precision |  |  | — |
| inpos | boolean |  |  | — |
| update_time | timestamp with time zone |  |  | — |


## Database: `exposure.headers`

Not surfaced by an `Exposure` accessor -- query `exposure.headers` directly via `telemetry_mining.db.fetch_df`, or add a custom `TableSource`. (Source `—` throughout.)

| Field | Type | Description | Example value | Source |
|---|---|---|---|---|
| exposure_id | integer |  |  | — |
| header_name | text |  |  | — |
| header_value | text |  |  | — |


## Database: `telemetry.guider_centroids`

Per-frame table -- one row per guider frame. `exp.guider_centroids` selects a fixed column list (`frame`, `time_recorded`, `obstime`, `seeing`, `nstars`, `ngfas`, `combined_x`/`combined_y`, `tcs_correction_ra`/`tcs_correction_dec`, `rotation`); the other columns (shown as `—`) come from querying `telemetry.guider_centroids` directly via `telemetry_mining.db.fetch_df` or a custom `TableSource`.

| Field | Type | Description | Example value | Source |
|---|---|---|---|---|
| guider_centroids | integer |  | 4396919 | — |
| combined_x | double precision | Combined guiding correction, X (arcsec or similar) | 0.7203623253644624 | `guider_centroids['combined_x']` |
| combined_y | double precision | Combined guiding correction, Y | 0.7453352122020355 | `guider_centroids['combined_y']` |
| time_recorded | timestamp with time zone | DB insert timestamp | 2026-07-15 11:31:40.947337+00:00 | `guider_centroids['time_recorded']` |
| dos_instance | text |  | desi_20260714 | — |
| row_status | text |  | M | — |
| row_status_time | timestamp with time zone |  | 2026-07-15 11:31:40.948195+00:00 | — |
| row_status_user | text |  | desi_writer | — |
| seeing | double precision | Per-frame seeing estimate | 1.0448253242182666 | `guider_centroids['seeing']` |
| nstars | integer | Number of guide stars used this frame | 11 | `guider_centroids['nstars']` |
| guide0_0 | jsonb |  | {'sn': 113.32468069047451, 'fit': 0.17543654525638538, 'f... | — |
| guide0_1 | jsonb |  | {'sn': 7.615476538277707, 'fit': None, 'fwhm': None, 'ali... | — |
| guide2_0 | jsonb |  | {'sn': 31.069851787128904, 'fit': 3.147847868950959, 'fwh... | — |
| guide2_1 | jsonb |  | {'sn': 27.100489126328508, 'fit': None, 'fwhm': None, 'al... | — |
| guide3_0 | jsonb |  | {'sn': 52.76180493299028, 'fit': 0.5508541036586253, 'fwh... | — |
| guide3_1 | jsonb |  | {'sn': 19.219949243873362, 'fit': None, 'fwhm': None, 'al... | — |
| guide5_0 | jsonb |  | {'sn': 71.80450944999073, 'fit': 0.5753848232853167, 'fwh... | — |
| guide5_1 | jsonb |  | None | — |
| guide7_0 | jsonb |  | {'sn': 44.990108368233784, 'fit': 0.7842074546414279, 'fw... | — |
| guide7_1 | jsonb |  | {'sn': 11.023032476912562, 'fit': None, 'fwhm': None, 'al... | — |
| guide8_0 | jsonb |  | {'sn': 96.56792110743447, 'fit': 0.039098040618436775, 'f... | — |
| guide8_1 | jsonb |  | {'sn': 5.321525828444858, 'fit': None, 'fwhm': None, 'ali... | — |
| pixel_scale | double precision | Plate scale (arcsec/pixel) | 0.205 | — |
| tcs_correction_ra | double precision | RA correction sent to TCS this frame | 0.14169526939918978 | `guider_centroids['tcs_correction_ra']` |
| tcs_correction_dec | double precision | Dec correction sent to TCS this frame | 0.15898000076269417 | `guider_centroids['tcs_correction_dec']` |
| guiding | integer | Whether active guiding was engaged this frame | 1 | — |
| send_guide_corrections | integer | Whether corrections were actually sent to the TCS | 1 | — |
| expid | integer | Exposure ID | 361286 | — |
| rotation | double precision | Field rotation estimate | -2.34187 | `guider_centroids['rotation']` |
| frame | integer | Guider frame number within the exposure (1-indexed) | 111 | `guider_centroids['frame']` |
| ngfas | integer | Number of GFA cameras contributing this frame | 6 | `guider_centroids['ngfas']` |
| obstime | timestamp with time zone | Guider frame observation timestamp | 2026-07-15 11:31:32.265141+00:00 | `guider_centroids['obstime']` |


## Database: `telemetry.environmentmonitor_telescope`

Time-windowed telemetry -- reach any column with `exp.telemetry('environmentmonitor_telescope', columns=['<col>'])` (returns the rows within the exposure's time window). For a single nearest/window scalar usable in `select_exposures`, register a `TelemetryField(name=..., table='environmentmonitor_telescope', columns=['<col>'])` and use the spec `"telemetry.<name>"`.

| Field | Type | Description | Example value | Source |
|---|---|---|---|---|
| environmentmonitor_telescope | integer |  | 37521803 | `exp.telemetry('environmentmonitor_telescope', columns=['environmentmonitor_telescope'])` |
| telescope_timestamp | text |  | 2026-07-17 17:23:32 | `exp.telemetry('environmentmonitor_telescope', columns=['telescope_timestamp'])` |
| mirror_avg_temp | double precision | Average mirror temperature across sensors | 18.928 | `exp.telemetry('environmentmonitor_telescope', columns=['mirror_avg_temp'])` |
| mirror_desired_temp | double precision | Mirror thermal control setpoint | 19.0 | `exp.telemetry('environmentmonitor_telescope', columns=['mirror_desired_temp'])` |
| servo_setpoint | double precision |  | 19.0 | `exp.telemetry('environmentmonitor_telescope', columns=['servo_setpoint'])` |
| air_temp | double precision | Air temperature at telescope | 18.725 | `exp.telemetry('environmentmonitor_telescope', columns=['air_temp'])` |
| air_dewpoint | double precision |  | 13.267 | `exp.telemetry('environmentmonitor_telescope', columns=['air_dewpoint'])` |
| air_flow | double precision |  | 4.395 | `exp.telemetry('environmentmonitor_telescope', columns=['air_flow'])` |
| probe1_humidity | double precision |  | 0.0 | `exp.telemetry('environmentmonitor_telescope', columns=['probe1_humidity'])` |
| probe1_temp | double precision |  | 0.0 | `exp.telemetry('environmentmonitor_telescope', columns=['probe1_temp'])` |
| probe2_humidity | double precision |  | 0.0 | `exp.telemetry('environmentmonitor_telescope', columns=['probe2_humidity'])` |
| probe2_temp | double precision |  | 0.0 | `exp.telemetry('environmentmonitor_telescope', columns=['probe2_temp'])` |
| flowrate_in | double precision |  | 0.0 | `exp.telemetry('environmentmonitor_telescope', columns=['flowrate_in'])` |
| flowrate_out | double precision |  | 0.0 | `exp.telemetry('environmentmonitor_telescope', columns=['flowrate_out'])` |
| mirror_rtd_temp | double precision |  | 19.13 | `exp.telemetry('environmentmonitor_telescope', columns=['mirror_rtd_temp'])` |
| mirror_nib_temp | double precision |  | 19.13 | `exp.telemetry('environmentmonitor_telescope', columns=['mirror_nib_temp'])` |
| mirror_eib_temp | double precision |  | 19.4 | `exp.telemetry('environmentmonitor_telescope', columns=['mirror_eib_temp'])` |
| mirror_sib_temp | double precision |  | 19.3 | `exp.telemetry('environmentmonitor_telescope', columns=['mirror_sib_temp'])` |
| mirror_wib_temp | double precision |  | 19.2 | `exp.telemetry('environmentmonitor_telescope', columns=['mirror_wib_temp'])` |
| mirror_nob_temp | double precision |  | 19.2 | `exp.telemetry('environmentmonitor_telescope', columns=['mirror_nob_temp'])` |
| mirror_eob_temp | double precision |  | 19.1 | `exp.telemetry('environmentmonitor_telescope', columns=['mirror_eob_temp'])` |
| mirror_sob_temp | double precision |  | 19.1 | `exp.telemetry('environmentmonitor_telescope', columns=['mirror_sob_temp'])` |
| mirror_wob_temp | double precision |  | 19.0 | `exp.telemetry('environmentmonitor_telescope', columns=['mirror_wob_temp'])` |
| mirror_nit_temp | double precision |  | 19.1 | `exp.telemetry('environmentmonitor_telescope', columns=['mirror_nit_temp'])` |
| mirror_eit_temp | double precision |  | 19.1 | `exp.telemetry('environmentmonitor_telescope', columns=['mirror_eit_temp'])` |
| mirror_sit_temp | double precision |  | 19.0 | `exp.telemetry('environmentmonitor_telescope', columns=['mirror_sit_temp'])` |
| mirror_wit_temp | double precision |  | 18.9 | `exp.telemetry('environmentmonitor_telescope', columns=['mirror_wit_temp'])` |
| mirror_not_temp | double precision |  | 18.9 | `exp.telemetry('environmentmonitor_telescope', columns=['mirror_not_temp'])` |
| mirror_eot_temp | double precision |  | 18.9 | `exp.telemetry('environmentmonitor_telescope', columns=['mirror_eot_temp'])` |
| mirror_sot_temp | double precision |  | 18.9 | `exp.telemetry('environmentmonitor_telescope', columns=['mirror_sot_temp'])` |
| mirror_wot_temp | double precision |  | 18.8 | `exp.telemetry('environmentmonitor_telescope', columns=['mirror_wot_temp'])` |
| glycol_in_temp | double precision |  | 7.4 | `exp.telemetry('environmentmonitor_telescope', columns=['glycol_in_temp'])` |
| glycol_out_temp | double precision |  | 19.2 | `exp.telemetry('environmentmonitor_telescope', columns=['glycol_out_temp'])` |
| air_in_temp | double precision |  | 19.9 | `exp.telemetry('environmentmonitor_telescope', columns=['air_in_temp'])` |
| air_out_temp | double precision |  | 18.6 | `exp.telemetry('environmentmonitor_telescope', columns=['air_out_temp'])` |
| truss_ntt_temp | double precision |  | 19.2 | `exp.telemetry('environmentmonitor_telescope', columns=['truss_ntt_temp'])` |
| truss_ett_temp | double precision |  | 19.2 | `exp.telemetry('environmentmonitor_telescope', columns=['truss_ett_temp'])` |
| truss_stt_temp | double precision |  | 19.5 | `exp.telemetry('environmentmonitor_telescope', columns=['truss_stt_temp'])` |
| truss_wtt_temp | double precision |  | 19.1 | `exp.telemetry('environmentmonitor_telescope', columns=['truss_wtt_temp'])` |
| truss_ntb_temp | double precision |  | 19.1 | `exp.telemetry('environmentmonitor_telescope', columns=['truss_ntb_temp'])` |
| truss_etb_temp | double precision |  | 8.7 | `exp.telemetry('environmentmonitor_telescope', columns=['truss_etb_temp'])` |
| truss_stb_temp | double precision |  | 19.1 | `exp.telemetry('environmentmonitor_telescope', columns=['truss_stb_temp'])` |
| truss_wtb_temp | double precision |  | 18.9 | `exp.telemetry('environmentmonitor_telescope', columns=['truss_wtb_temp'])` |
| truss_sts_temp | double precision |  | 10.8 | `exp.telemetry('environmentmonitor_telescope', columns=['truss_sts_temp'])` |
| truss_tsb_temp | double precision |  | 20.1 | `exp.telemetry('environmentmonitor_telescope', columns=['truss_tsb_temp'])` |
| truss_tsm_temp | double precision |  | 20.0 | `exp.telemetry('environmentmonitor_telescope', columns=['truss_tsm_temp'])` |
| truss_tst_temp | double precision |  | 19.8 | `exp.telemetry('environmentmonitor_telescope', columns=['truss_tst_temp'])` |
| topring_s_temp | double precision |  | 19.7 | `exp.telemetry('environmentmonitor_telescope', columns=['topring_s_temp'])` |
| topring_w_temp | double precision |  | 19.6 | `exp.telemetry('environmentmonitor_telescope', columns=['topring_w_temp'])` |
| hinge_s_temp | double precision |  | 19.8 | `exp.telemetry('environmentmonitor_telescope', columns=['hinge_s_temp'])` |
| hinge_w_temp | double precision |  | 22.3 | `exp.telemetry('environmentmonitor_telescope', columns=['hinge_w_temp'])` |
| chimney_os_temp | double precision |  | 0.0 | `exp.telemetry('environmentmonitor_telescope', columns=['chimney_os_temp'])` |
| chimney_ow_temp | double precision |  | 0.0 | `exp.telemetry('environmentmonitor_telescope', columns=['chimney_ow_temp'])` |
| chimney_ib_temp | double precision |  | 0.0 | `exp.telemetry('environmentmonitor_telescope', columns=['chimney_ib_temp'])` |
| chimney_im_temp | double precision |  | 0.0 | `exp.telemetry('environmentmonitor_telescope', columns=['chimney_im_temp'])` |
| chimney_it_temp | double precision |  | 18.9 | `exp.telemetry('environmentmonitor_telescope', columns=['chimney_it_temp'])` |
| centersection_i_temp | double precision |  | 19.0 | `exp.telemetry('environmentmonitor_telescope', columns=['centersection_i_temp'])` |
| centersection_o_temp | double precision |  | 19.4 | `exp.telemetry('environmentmonitor_telescope', columns=['centersection_o_temp'])` |
| primarycell_i_temp | double precision |  | 19.3 | `exp.telemetry('environmentmonitor_telescope', columns=['primarycell_i_temp'])` |
| primarycell_o_temp | double precision |  | 19.2 | `exp.telemetry('environmentmonitor_telescope', columns=['primarycell_o_temp'])` |
| casscage_i_temp | double precision |  | 6.6 | `exp.telemetry('environmentmonitor_telescope', columns=['casscage_i_temp'])` |
| casscage_o_temp | double precision |  | 19.8 | `exp.telemetry('environmentmonitor_telescope', columns=['casscage_o_temp'])` |
| decbore_temp | double precision |  | 11.5 | `exp.telemetry('environmentmonitor_telescope', columns=['decbore_temp'])` |
| mirror_status | text |  | soft air | `exp.telemetry('environmentmonitor_telescope', columns=['mirror_status'])` |
| time_recorded | timestamp with time zone | Telemetry timestamp (timestamptz) -- the time_column used by query_nearest/query_window | 2026-07-17 17:23:23.149755+00:00 | `exp.telemetry('environmentmonitor_telescope', columns=['time_recorded'])` |
| dos_instance | text |  | extern | `exp.telemetry('environmentmonitor_telescope', columns=['dos_instance'])` |
| row_status | text |  | M | `exp.telemetry('environmentmonitor_telescope', columns=['row_status'])` |
| row_status_time | timestamp with time zone |  | 2026-07-17 17:23:23.155315+00:00 | `exp.telemetry('environmentmonitor_telescope', columns=['row_status_time'])` |
| row_status_user | text |  | desi_writer | `exp.telemetry('environmentmonitor_telescope', columns=['row_status_user'])` |
| mirror_temp | double precision | Primary mirror temperature | 18.95 | `exp.telemetry('environmentmonitor_telescope', columns=['mirror_temp'])` |
| truss_temp | double precision |  | 19.967 | `exp.telemetry('environmentmonitor_telescope', columns=['truss_temp'])` |
| mirror_cooling | integer |  | 1 | `exp.telemetry('environmentmonitor_telescope', columns=['mirror_cooling'])` |
| wind_gust | integer | Wind-gust event flag/count | 0 | `exp.telemetry('environmentmonitor_telescope', columns=['wind_gust'])` |
| wind_shake | integer | Wind-shake event flag/count | 0 | `exp.telemetry('environmentmonitor_telescope', columns=['wind_shake'])` |
| between_twilight | integer | Whether this record falls between evening/morning twilight | 0 | `exp.telemetry('environmentmonitor_telescope', columns=['between_twilight'])` |


## Database: `telemetry.environmentmonitor_tower`

Time-windowed telemetry -- reach any column with `exp.telemetry('environmentmonitor_tower', columns=['<col>'])` (returns the rows within the exposure's time window). For a single nearest/window scalar usable in `select_exposures`, register a `TelemetryField(name=..., table='environmentmonitor_tower', columns=['<col>'])` and use the spec `"telemetry.<name>"`.

| Field | Type | Description | Example value | Source |
|---|---|---|---|---|
| environmentmonitor_tower | integer |  | 37521765 | `exp.telemetry('environmentmonitor_tower', columns=['environmentmonitor_tower'])` |
| tower_timestamp | text | Tower-side timestamp (text, distinct format from time_recorded) | 2026-07-17 17:21:08 | `exp.telemetry('environmentmonitor_tower', columns=['tower_timestamp'])` |
| wind_speed | double precision | Wind speed at the tower anemometer | 1.1 | `exp.telemetry('environmentmonitor_tower', columns=['wind_speed'])` |
| wind_direction | double precision | Wind direction | 159.7 | `exp.telemetry('environmentmonitor_tower', columns=['wind_direction'])` |
| humidity | double precision |  | 93.7 | `exp.telemetry('environmentmonitor_tower', columns=['humidity'])` |
| pressure | double precision |  | 796.9 | `exp.telemetry('environmentmonitor_tower', columns=['pressure'])` |
| temperature | double precision |  | 16.6 | `exp.telemetry('environmentmonitor_tower', columns=['temperature'])` |
| dewpoint | double precision |  | 15.6 | `exp.telemetry('environmentmonitor_tower', columns=['dewpoint'])` |
| split | double precision |  | 1.0 | `exp.telemetry('environmentmonitor_tower', columns=['split'])` |
| gust | double precision | Gust speed | 1.9 | `exp.telemetry('environmentmonitor_tower', columns=['gust'])` |
| time_recorded | timestamp with time zone | Telemetry timestamp (timestamptz) -- used for nearest/window queries | 2026-07-17 17:23:23.784262+00:00 | `exp.telemetry('environmentmonitor_tower', columns=['time_recorded'])` |
| dos_instance | text |  | extern | `exp.telemetry('environmentmonitor_tower', columns=['dos_instance'])` |
| row_status | text |  | M | `exp.telemetry('environmentmonitor_tower', columns=['row_status'])` |
| row_status_time | timestamp with time zone |  | 2026-07-17 17:23:23.787637+00:00 | `exp.telemetry('environmentmonitor_tower', columns=['row_status_time'])` |
| row_status_user | text |  | desi_writer | `exp.telemetry('environmentmonitor_tower', columns=['row_status_user'])` |
| dimm | double precision |  | 1.7369 | `exp.telemetry('environmentmonitor_tower', columns=['dimm'])` |
| dimm_timestamp | text |  | 2026-07-11 06:22:11 | `exp.telemetry('environmentmonitor_tower', columns=['dimm_timestamp'])` |
| between_twilight | integer |  | 0 | `exp.telemetry('environmentmonitor_tower', columns=['between_twilight'])` |


## Database: `telemetry.environmentmonitor_dust`

Time-windowed telemetry -- reach any column with `exp.telemetry('environmentmonitor_dust', columns=['<col>'])` (returns the rows within the exposure's time window). For a single nearest/window scalar usable in `select_exposures`, register a `TelemetryField(name=..., table='environmentmonitor_dust', columns=['<col>'])` and use the spec `"telemetry.<name>"`.

| Field | Type | Description | Example value | Source |
|---|---|---|---|---|
| environmentmonitor_dust | integer |  | 3904989 | `exp.telemetry('environmentmonitor_dust', columns=['environmentmonitor_dust'])` |
| mayall_particle_1_timestamp | text | Per-sensor text timestamp -- prefer time_recorded for consistency across telemetry tables | 2025-10-01 16:27:31 | `exp.telemetry('environmentmonitor_dust', columns=['mayall_particle_1_timestamp'])` |
| mayall_particle_1_micron_pt3 | integer |  | 6463 | `exp.telemetry('environmentmonitor_dust', columns=['mayall_particle_1_micron_pt3'])` |
| mayall_particle_1_micron_pt5 | integer |  | 988 | `exp.telemetry('environmentmonitor_dust', columns=['mayall_particle_1_micron_pt5'])` |
| mayall_particle_1_micron_5 | integer | Mayall dust sensor 1, particle count >=5 micron. Table only has data from 2025-10-21 onward -- always pass max_delta_seconds when querying older exposures | 18 | `exp.telemetry('environmentmonitor_dust', columns=['mayall_particle_1_micron_5'])` |
| mayall_particle_1_micron_10 | integer |  | 7 | `exp.telemetry('environmentmonitor_dust', columns=['mayall_particle_1_micron_10'])` |
| mayall_particle_1_background_light | integer |  | 249 | `exp.telemetry('environmentmonitor_dust', columns=['mayall_particle_1_background_light'])` |
| wiyn_particle_1_timestamp | text |  | 2026-07-17 17:22:08 | `exp.telemetry('environmentmonitor_dust', columns=['wiyn_particle_1_timestamp'])` |
| wiyn_particle_1_micron_pt3 | integer |  | 15705 | `exp.telemetry('environmentmonitor_dust', columns=['wiyn_particle_1_micron_pt3'])` |
| wiyn_particle_1_micron_pt5 | integer |  | 1192 | `exp.telemetry('environmentmonitor_dust', columns=['wiyn_particle_1_micron_pt5'])` |
| wiyn_particle_1_micron_5 | integer |  | 1 | `exp.telemetry('environmentmonitor_dust', columns=['wiyn_particle_1_micron_5'])` |
| wiyn_particle_1_micron_10 | integer |  | 0 | `exp.telemetry('environmentmonitor_dust', columns=['wiyn_particle_1_micron_10'])` |
| wiyn_particle_1_background_light | integer |  | 4248 | `exp.telemetry('environmentmonitor_dust', columns=['wiyn_particle_1_background_light'])` |
| wiyn_particle_2_timestamp | text |  | 2026-07-17 17:22:06 | `exp.telemetry('environmentmonitor_dust', columns=['wiyn_particle_2_timestamp'])` |
| wiyn_particle_2_micron_pt3 | integer |  | 9900 | `exp.telemetry('environmentmonitor_dust', columns=['wiyn_particle_2_micron_pt3'])` |
| wiyn_particle_2_micron_pt5 | integer |  | 859 | `exp.telemetry('environmentmonitor_dust', columns=['wiyn_particle_2_micron_pt5'])` |
| wiyn_particle_2_micron_5 | integer |  | 0 | `exp.telemetry('environmentmonitor_dust', columns=['wiyn_particle_2_micron_5'])` |
| wiyn_particle_2_micron_10 | integer |  | 0 | `exp.telemetry('environmentmonitor_dust', columns=['wiyn_particle_2_micron_10'])` |
| wiyn_particle_2_background_light | integer |  | 1757 | `exp.telemetry('environmentmonitor_dust', columns=['wiyn_particle_2_background_light'])` |
| time_recorded | timestamp with time zone | Telemetry timestamp (timestamptz) | 2026-07-17 17:23:22.481548+00:00 | `exp.telemetry('environmentmonitor_dust', columns=['time_recorded'])` |
| between_twilight | integer |  | 0 | `exp.telemetry('environmentmonitor_dust', columns=['between_twilight'])` |
| dos_instance | text |  | extern | `exp.telemetry('environmentmonitor_dust', columns=['dos_instance'])` |
| row_status | text |  | M | `exp.telemetry('environmentmonitor_dust', columns=['row_status'])` |
| row_status_time | timestamp with time zone |  | 2026-07-17 17:23:22.485406+00:00 | `exp.telemetry('environmentmonitor_dust', columns=['row_status_time'])` |
| row_status_user | text |  | desi_writer | `exp.telemetry('environmentmonitor_dust', columns=['row_status_user'])` |
| mayall_particle_2_timestamp | text |  | 2026-07-17 17:22:13 | `exp.telemetry('environmentmonitor_dust', columns=['mayall_particle_2_timestamp'])` |
| mayall_particle_2_micron_pt3 | integer |  | 1132230 | `exp.telemetry('environmentmonitor_dust', columns=['mayall_particle_2_micron_pt3'])` |
| mayall_particle_2_micron_pt5 | integer |  | 249 | `exp.telemetry('environmentmonitor_dust', columns=['mayall_particle_2_micron_pt5'])` |
| mayall_particle_2_micron_5 | integer |  | 0 | `exp.telemetry('environmentmonitor_dust', columns=['mayall_particle_2_micron_5'])` |
| mayall_particle_2_micron_10 | integer |  | 0 | `exp.telemetry('environmentmonitor_dust', columns=['mayall_particle_2_micron_10'])` |
| mayall_particle_2_background_light | integer |  | 8467 | `exp.telemetry('environmentmonitor_dust', columns=['mayall_particle_2_background_light'])` |


*(93 tables total in the `telemetry` schema -- only the ones this project actually queries are listed here. To inspect another: `SELECT column_name, data_type FROM information_schema.columns WHERE table_schema='telemetry' AND table_name='...'` via `telemetry_mining.db.fetch_all`.)*


## Database: `alarms.alarms`

The DESI **alarm log**, in its own `alarms` schema. Exposed via `Exposure.alarms()`
(per-exposure — alarms within the exposure's time window) and `find_alarms(...)` (global
search by `alarm_id`/`level`/`component`/time/message); see `API.md`. This section is **hand-maintained** (not emitted by
`scripts/build_fields_glossary.py`, which samples `exposure`/`telemetry`/offline files
only) and carries no example values — the `alarms` schema isn't reachable from the
offline development environment; sample it against a live DB if wanted.

`Exposure.alarms()` selects a default column set; the boolean **alarm-handler routing
flags** (which handler each alarm triggers) and acknowledgement bookkeeping are
deliberately omitted — pass `columns=` to include them.

| Field | Type | Description | In `exp.alarms()` default? |
|---|---|---|---|
| id | integer | Auto-increment primary key (`nextval('alarms_id_seq')`) | ✅ |
| time_recorded | timestamp with time zone | When the alarm was recorded — the time-window key (indexed) | ✅ |
| level | text | Severity: `CRITICAL` / `ALERT` / `WARNING` / `EVENT` (enforced by `alarms_level_check`) | ✅ |
| component | text | Subsystem/component that raised the alarm | ✅ |
| instance | text | DOS instance that raised it (nullable) | ✅ |
| message | text | Human-readable alarm message | ✅ |
| alarm_id | integer | Alarm-type identifier (nullable) — distinct from the row `id` | ⬜ `columns=[…, 'alarm_id']` |
| sve_enabled, logbook, twitter, tcs, ocs, stop_exposure_loop, email_enabled, shutdown_gfa, shutdown_petalcontroller, slack | boolean | Alarm-handler **routing flags** — which handler this alarm triggers (dispatch control, not content) | ⬜ omitted |
| acknowledged_by | text | Who acknowledged the alarm (nullable; a trigger stamps `when_acknowledged` on update) | ⬜ omitted |
| when_acknowledged | timestamp with time zone | When it was acknowledged (nullable) | ⬜ omitted |
| ocs_msg, sms | text | OCS / SMS dispatch text (nullable) | ⬜ omitted |


## Offline per-camera spectra: cframe `FIBERMAP` extension

Live example: camera z3, expid 359483. Per-fiber table: `exp.cframe_table(camera)` needs a `camera` argument, so in a resolve_spec use a callable, e.g. `lambda exp: exp.cframe_table('b0')['<col>']`.

| Field | Type | Description | Example value | Source |
|---|---|---|---|---|
| TARGETID |  | Unique target identifier | 39627577605754915 | `exp.cframe_table(camera)['TARGETID']` |
| PETAL_LOC |  | Petal (spectrograph unit) number 0-9 | 3 | `exp.cframe_table(camera)['PETAL_LOC']` |
| DEVICE_LOC |  | Positioner device location within the petal | 69 | `exp.cframe_table(camera)['DEVICE_LOC']` |
| LOCATION |  | PETAL_LOC*1000+DEVICE_LOC (confirmed identity) | 3069 | `exp.cframe_table(camera)['LOCATION']` |
| FIBER |  | Fiber number -- confirmed to be the actual row-order key (sorted ascending), not DEVICE_LOC | 1500 | `exp.cframe_table(camera)['FIBER']` |
| FIBERSTATUS |  |  | 0 | `exp.cframe_table(camera)['FIBERSTATUS']` |
| TARGET_RA |  |  | 215.61054408321553 | `exp.cframe_table(camera)['TARGET_RA']` |
| TARGET_DEC |  |  | -8.707479987403664 | `exp.cframe_table(camera)['TARGET_DEC']` |
| DESINAME |  |  | DESI J215.6105-08.7074 | `exp.cframe_table(camera)['DESINAME']` |
| PMRA |  |  | -3.8371637 | `exp.cframe_table(camera)['PMRA']` |
| PMDEC |  |  | -4.191923 | `exp.cframe_table(camera)['PMDEC']` |
| REF_EPOCH |  |  | 2015.5 | `exp.cframe_table(camera)['REF_EPOCH']` |
| LAMBDA_REF |  |  | 5400.0 | `exp.cframe_table(camera)['LAMBDA_REF']` |
| FA_TARGET |  |  | 2305843009213693952 | `exp.cframe_table(camera)['FA_TARGET']` |
| FA_TYPE |  |  | 1 | `exp.cframe_table(camera)['FA_TYPE']` |
| OBJTYPE |  | Object type classification | TGT | `exp.cframe_table(camera)['OBJTYPE']` |
| FIBERASSIGN_X |  |  | 123.23582 | `exp.cframe_table(camera)['FIBERASSIGN_X']` |
| FIBERASSIGN_Y |  |  | 72.52518 | `exp.cframe_table(camera)['FIBERASSIGN_Y']` |
| PRIORITY |  |  | 1500 | `exp.cframe_table(camera)['PRIORITY']` |
| SUBPRIORITY |  |  | 0.6081359900860978 | `exp.cframe_table(camera)['SUBPRIORITY']` |
| OBSCONDITIONS |  |  | 516 | `exp.cframe_table(camera)['OBSCONDITIONS']` |
| RELEASE |  |  | 9010 | `exp.cframe_table(camera)['RELEASE']` |
| BRICKNAME |  |  | 2155m087 | `exp.cframe_table(camera)['BRICKNAME']` |
| BRICKID |  |  | 280986 | `exp.cframe_table(camera)['BRICKID']` |
| BRICK_OBJID |  |  | 4131 | `exp.cframe_table(camera)['BRICK_OBJID']` |
| MORPHTYPE |  | Photometric morphology classification (e.g. PSF) | PSF | `exp.cframe_table(camera)['MORPHTYPE']` |
| EBV |  |  | 0.053330027 | `exp.cframe_table(camera)['EBV']` |
| FLUX_G |  |  | 76.58968 | `exp.cframe_table(camera)['FLUX_G']` |
| FLUX_R |  |  | 111.96188 | `exp.cframe_table(camera)['FLUX_R']` |
| FLUX_Z |  |  | 131.20618 | `exp.cframe_table(camera)['FLUX_Z']` |
| FLUX_W1 |  |  | 35.954075 | `exp.cframe_table(camera)['FLUX_W1']` |
| FLUX_W2 |  |  | 19.044018 | `exp.cframe_table(camera)['FLUX_W2']` |
| FLUX_IVAR_G |  |  | 133.21568 | `exp.cframe_table(camera)['FLUX_IVAR_G']` |
| FLUX_IVAR_R |  |  | 98.12086 | `exp.cframe_table(camera)['FLUX_IVAR_R']` |
| FLUX_IVAR_Z |  |  | 47.98112 | `exp.cframe_table(camera)['FLUX_IVAR_Z']` |
| FLUX_IVAR_W1 |  |  | 2.2671554 | `exp.cframe_table(camera)['FLUX_IVAR_W1']` |
| FLUX_IVAR_W2 |  |  | 0.5556476 | `exp.cframe_table(camera)['FLUX_IVAR_W2']` |
| FIBERFLUX_G |  |  | 59.570496 | `exp.cframe_table(camera)['FIBERFLUX_G']` |
| FIBERFLUX_R |  |  | 87.08255 | `exp.cframe_table(camera)['FIBERFLUX_R']` |
| FIBERFLUX_Z |  |  | 102.05052 | `exp.cframe_table(camera)['FIBERFLUX_Z']` |
| FIBERTOTFLUX_G |  |  | 59.570496 | `exp.cframe_table(camera)['FIBERTOTFLUX_G']` |
| FIBERTOTFLUX_R |  |  | 87.08255 | `exp.cframe_table(camera)['FIBERTOTFLUX_R']` |
| FIBERTOTFLUX_Z |  |  | 102.05052 | `exp.cframe_table(camera)['FIBERTOTFLUX_Z']` |
| MASKBITS |  |  | 0 | `exp.cframe_table(camera)['MASKBITS']` |
| SERSIC |  |  | 0.0 | `exp.cframe_table(camera)['SERSIC']` |
| SHAPE_R |  |  | 0.0 | `exp.cframe_table(camera)['SHAPE_R']` |
| SHAPE_E1 |  |  | 0.0 | `exp.cframe_table(camera)['SHAPE_E1']` |
| SHAPE_E2 |  |  | 0.0 | `exp.cframe_table(camera)['SHAPE_E2']` |
| REF_ID |  |  | 6329550238201715584 | `exp.cframe_table(camera)['REF_ID']` |
| REF_CAT |  |  | G2 | `exp.cframe_table(camera)['REF_CAT']` |
| GAIA_PHOT_G_MEAN_MAG |  | Gaia G-band magnitude, used e.g. to select bright stars in linphi_splitflux.ipynb | 17.45347 | `exp.cframe_table(camera)['GAIA_PHOT_G_MEAN_MAG']` |
| GAIA_PHOT_BP_MEAN_MAG |  |  | 17.770653 | `exp.cframe_table(camera)['GAIA_PHOT_BP_MEAN_MAG']` |
| GAIA_PHOT_RP_MEAN_MAG |  |  | 16.930521 | `exp.cframe_table(camera)['GAIA_PHOT_RP_MEAN_MAG']` |
| PARALLAX |  |  | 0.035127345 | `exp.cframe_table(camera)['PARALLAX']` |
| PHOTSYS |  |  | S | `exp.cframe_table(camera)['PHOTSYS']` |
| PRIORITY_INIT |  |  | 1500 | `exp.cframe_table(camera)['PRIORITY_INIT']` |
| NUMOBS_INIT |  |  | 2 | `exp.cframe_table(camera)['NUMOBS_INIT']` |
| DESI_TARGET |  | Targeting bitmask, main DARK/BRIGHT survey -- includes STD_FAINT/STD_WD/STD_BRIGHT standard-star bits; decode with desitarget.targetmask.desi_mask | 2305843009213693952 | `exp.cframe_table(camera)['DESI_TARGET']` |
| BGS_TARGET |  | BGS-specific targeting bitmask; decode with desitarget.targetmask.bgs_mask | 0 | `exp.cframe_table(camera)['BGS_TARGET']` |
| MWS_TARGET |  | MWS-specific targeting bitmask -- also where BACKUP-program exposures (program='BACKUP') flag their standard stars (GAIA_STD_FAINT/GAIA_STD_WD/GAIA_STD_BRIGHT) instead of DESI_TARGET -- confirmed real: a BACKUP exposure had 0/297 calibstars fibers match DESI_TARGET's STD bits, 297/297 match MWS_TARGET's GAIA_STD bits instead; decode with desitarget.targetmask.mws_mask | 1280 | `exp.cframe_table(camera)['MWS_TARGET']` |
| SCND_TARGET |  | Secondary-program targeting bitmask; decode with desitarget.targetmask.scnd_mask | 0 | `exp.cframe_table(camera)['SCND_TARGET']` |
| PLATE_RA |  |  | 215.61054408321553 | `exp.cframe_table(camera)['PLATE_RA']` |
| PLATE_DEC |  |  | -8.707479987403664 | `exp.cframe_table(camera)['PLATE_DEC']` |
| NUM_ITER |  |  | 2 | `exp.cframe_table(camera)['NUM_ITER']` |
| FIBER_X |  |  | 123.22671284834107 | `exp.cframe_table(camera)['FIBER_X']` |
| FIBER_Y |  |  | 72.52075337077324 | `exp.cframe_table(camera)['FIBER_Y']` |
| DELTA_X |  |  | -0.0017128483410754677 | `exp.cframe_table(camera)['DELTA_X']` |
| DELTA_Y |  |  | -0.003753370773237464 | `exp.cframe_table(camera)['DELTA_Y']` |
| FIBER_RA |  |  | 215.61053716844762 | `exp.cframe_table(camera)['FIBER_RA']` |
| FIBER_DEC |  |  | -8.707464676169353 | `exp.cframe_table(camera)['FIBER_DEC']` |
| EXPTIME |  |  | 1065.056 | `exp.cframe_table(camera)['EXPTIME']` |
| PSF_TO_FIBER_SPECFLUX |  |  | 0.789 | `exp.cframe_table(camera)['PSF_TO_FIBER_SPECFLUX']` |
| FLAT_TO_PSF_FLUX |  |  | 1.0204433 | `exp.cframe_table(camera)['FLAT_TO_PSF_FLUX']` |
| HELIOCOR_OFFSET |  |  | -4.1560915e-07 | `exp.cframe_table(camera)['HELIOCOR_OFFSET']` |


## Offline per-camera spectra: cframe `SCORES` extension

Row-aligned with FIBERMAP (no location columns of its own -- see project memory). Per-fiber table: `exp.cframe_table(camera)` needs a `camera` argument, so in a resolve_spec use a callable, e.g. `lambda exp: exp.cframe_table('b0')['<col>']`.

| Field | Type | Description | Example value | Source |
|---|---|---|---|---|
| SUM_RAW_COUNT_Z |  |  | 5759298.819549561 | `exp.cframe_table(camera)['SUM_RAW_COUNT_Z']` |
| MEDIAN_RAW_COUNT_Z |  |  | 2022.9913330073525 | `exp.cframe_table(camera)['MEDIAN_RAW_COUNT_Z']` |
| MEDIAN_RAW_SNR_Z |  |  | 39.60517239138913 | `exp.cframe_table(camera)['MEDIAN_RAW_SNR_Z']` |
| SUM_FFLAT_COUNT_Z |  |  | 5200799.131333322 | `exp.cframe_table(camera)['SUM_FFLAT_COUNT_Z']` |
| MEDIAN_FFLAT_COUNT_Z |  |  | 1833.8096687690395 | `exp.cframe_table(camera)['MEDIAN_FFLAT_COUNT_Z']` |
| MEDIAN_FFLAT_SNR_Z |  |  | 39.2455173432341 | `exp.cframe_table(camera)['MEDIAN_FFLAT_SNR_Z']` |
| SUM_SKYSUB_COUNT_Z |  |  | 2929736.222333169 | `exp.cframe_table(camera)['SUM_SKYSUB_COUNT_Z']` |
| MEDIAN_SKYSUB_COUNT_Z |  |  | 1469.536623615407 | `exp.cframe_table(camera)['MEDIAN_SKYSUB_COUNT_Z']` |
| MEDIAN_SKYSUB_SNR_Z |  |  | 30.12359863552129 | `exp.cframe_table(camera)['MEDIAN_SKYSUB_SNR_Z']` |
| SUM_CALIB_COUNT_Z |  |  | 60388.37594276784 | `exp.cframe_table(camera)['SUM_CALIB_COUNT_Z']` |
| MEDIAN_CALIB_COUNT_Z |  | Median calibrated flux count, z camera (used by linphi_splitflux.ipynb) | 27.184375475074667 | `exp.cframe_table(camera)['MEDIAN_CALIB_COUNT_Z']` |
| MEDIAN_CALIB_SNR_Z |  | Median calibrated S/N, z camera | 28.32782720464347 | `exp.cframe_table(camera)['MEDIAN_CALIB_SNR_Z']` |
| TSNR2_BGS_Z |  | BGS template S/N^2 contribution, this fiber, z arm | 995.9690230942432 | `exp.cframe_table(camera)['TSNR2_BGS_Z']` |
| TSNR2_ELG_Z |  |  | 22.478929826823844 | `exp.cframe_table(camera)['TSNR2_ELG_Z']` |
| TSNR2_GPBBACKUP_Z |  |  | 9.577119315632603e-06 | `exp.cframe_table(camera)['TSNR2_GPBBACKUP_Z']` |
| TSNR2_GPBBRIGHT_Z |  |  | 1.1868104623687177e-06 | `exp.cframe_table(camera)['TSNR2_GPBBRIGHT_Z']` |
| TSNR2_GPBDARK_Z |  |  | 6.113418952129097e-06 | `exp.cframe_table(camera)['TSNR2_GPBDARK_Z']` |
| TSNR2_LRG_Z |  |  | 10.536826079902394 | `exp.cframe_table(camera)['TSNR2_LRG_Z']` |
| TSNR2_LYA_Z |  |  | 0.0 | `exp.cframe_table(camera)['TSNR2_LYA_Z']` |
| TSNR2_QSO_Z |  |  | 3.8857723109800943 | `exp.cframe_table(camera)['TSNR2_QSO_Z']` |


## Offline GFA summary: `EXPOSURE_SUMMARY_STRICT` extension

| Field | Type | Description | Example value | Source |
|---|---|---|---|---|
| EXPID |  | Exposure ID | 83522 | `gfa_row['EXPID']` |
| CUBE_INDEX |  |  | -1 | `gfa_row['CUBE_INDEX']` |
| NIGHT |  | Observing night | 20210405 | `gfa_row['NIGHT']` |
| EXPTIME |  | Guider's own per-frame exposure time (s) -- NOT the spectrograph EXPTIME, can differ substantially (e.g. 5s guider frame during a much longer science exposure) | 5.0 | `gfa_row['EXPTIME']` |
| FNAME_RAW |  |  | /global/cfs/cdirs/desi/spectro/data/20210405/00083522/gui... | `gfa_row['FNAME_RAW']` |
| SKYRA |  |  | 150.045192 | `gfa_row['SKYRA']` |
| SKYDEC |  |  | 2.27918 | `gfa_row['SKYDEC']` |
| PROGRAM |  |  | BRIGHT | `gfa_row['PROGRAM']` |
| MOON_ILLUMINATION |  | Fraction of the Moon illuminated (0-1) | 0.32165655238961327 | `gfa_row['MOON_ILLUMINATION']` |
| MOON_ZD_DEG |  | Moon zenith distance (deg) | 169.97905325303662 | `gfa_row['MOON_ZD_DEG']` |
| MOON_SEP_DEG |  | Moon-target angular separation (deg) | 151.56973009087207 | `gfa_row['MOON_SEP_DEG']` |
| KTERM |  | Extinction k-term used | 0.114 | `gfa_row['KTERM']` |
| FRACFLUX_NOMINAL_POINTSOURCE |  |  | 0.58176816 | `gfa_row['FRACFLUX_NOMINAL_POINTSOURCE']` |
| FRACFLUX_NOMINAL_ELG |  |  | 0.42423388 | `gfa_row['FRACFLUX_NOMINAL_ELG']` |
| FRACFLUX_NOMINAL_BGS |  |  | 0.19544029 | `gfa_row['FRACFLUX_NOMINAL_BGS']` |
| MJD |  |  | 59310.1223353314 | `gfa_row['MJD']` |
| FWHM_ASEC |  | Seeing FWHM (arcsec) -- confirmed NaN-free across all of EXPOSURE_SUMMARY_STRICT | 1.2810781090848906 | `gfa_row['FWHM_ASEC']` |
| TRANSPARENCY |  | Atmospheric transparency estimate | 0.07630297572569356 | `gfa_row['TRANSPARENCY']` |
| SKY_MAG_AB |  | Sky brightness, AB mag/arcsec^2 | 20.198798889675196 | `gfa_row['SKY_MAG_AB']` |
| FIBER_FRACFLUX |  | Fraction of flux captured within a fiber (point source) | 0.46873832443347047 | `gfa_row['FIBER_FRACFLUX']` |
| FIBER_FRACFLUX_ELG |  |  | 0.3516396983470239 | `gfa_row['FIBER_FRACFLUX_ELG']` |
| FIBER_FRACFLUX_BGS |  |  | 0.1651608369709665 | `gfa_row['FIBER_FRACFLUX_BGS']` |
| AIRMASS |  |  | 1.2476632872345048 | `gfa_row['AIRMASS']` |
| RADPROF_FWHM_ASEC |  |  | 1.3382835703547182 | `gfa_row['RADPROF_FWHM_ASEC']` |
| FIBERFAC |  | Fiber acceptance fraction (point source) | 0.05873999987469156 | `gfa_row['FIBERFAC']` |
| FIBERFAC_ELG |  | Fiber acceptance fraction, ELG profile | 0.06026796197292698 | `gfa_row['FIBERFAC_ELG']` |
| FIBERFAC_BGS |  | Fiber acceptance fraction, BGS profile | 0.0615441450052719 | `gfa_row['FIBERFAC_BGS']` |
| MINCONTRAST |  |  | 3.4190660995870124 | `gfa_row['MINCONTRAST']` |
| MAXCONTRAST |  |  | 5.552699726758177 | `gfa_row['MAXCONTRAST']` |


## Offline per-exposure QA: `exposure-qa-<expid>.fits` -- `FIBERQA` header (scalar QA summary)

**Correction to an earlier assumption in this project**: `FIBERQA` is not just these ~8 scalar keys -- see the table below this one. The header also repeats ~21 exposure-metadata keys already available elsewhere (NIGHT/EXPID/TILEID/EXPTIME/pointing/AIRMASS/etc.) -- omitted here as duplicates. `exp.fiberqa` exposes a curated 5-key dict (`NGOODFIB`, `NGOODPET`, `WORSTRDN`, `FPRMS2D`, `EFFTIME`); the other keys (shown as `—`) are read from the FIBERQA header directly via a callable.

| Field | Type | Description | Example value | Source |
|---|---|---|---|---|
| NGOODFIB | int | Number of fibers passing QA | 4362 | `fiberqa['NGOODFIB']` |
| NGOODPET | int | Number of petals passing QA | 10 | `fiberqa['NGOODPET']` |
| WORSTRDN | float | Worst (highest) CCD read noise across all cameras for this exposure | 4.5657738006904065 | `fiberqa['WORSTRDN']` |
| FPRMS2D | float | Fiber positioning RMS (2D), post-hoc QA -- confirmed distinct from db_row['posrms'] | 0.006449469234919501 | `fiberqa['FPRMS2D']` |
| EFFTIME | float | Pipeline effective time -- confirmed near-identical to redux_row['EFFTIME_SPEC'] for the same exposure | 230.07797 | `fiberqa['EFFTIME']` |
| SKY_MAG_G_SPEC | float | Whole-exposure sky brightness, g band, AB mag/arcsec^2 (distinct from PETALQA's per-petal SKY_MAG_G_SPEC) | 21.554023609456166 | — |
| SKY_MAG_R_SPEC | float | Whole-exposure sky brightness, r band | 20.84411935264965 | — |
| SKY_MAG_Z_SPEC | float | Whole-exposure sky brightness, z band | 19.01187014349819 | — |


## Offline per-exposure QA: `exposure-qa-<expid>.fits` -- `FIBERQA` table (per-fiber QA)

5000 rows -- one per fiber across the **whole focal plane** (not per-camera like cframe's 500-row FIBERMAP). Available as `Exposure.fiberqa_table` (DataFrame indexed by (PETAL_LOC, DEVICE_LOC), same shape as `cframe_table`).

| Field | Type | Description | Example value | Source |
|---|---|---|---|---|
| TARGETID | int64 | Unique target identifier | 48423634854746143 | `fiberqa_table['TARGETID']` (per-fiber table) |
| PETAL_LOC | int16 | Petal (spectrograph unit) number 0-9 | 0 | `fiberqa_table['PETAL_LOC']` (per-fiber table) |
| DEVICE_LOC | int32 | Positioner device location within the petal | 311 | `fiberqa_table['DEVICE_LOC']` (per-fiber table) |
| LOCATION | int64 | PETAL_LOC*1000+DEVICE_LOC | 311 | `fiberqa_table['LOCATION']` (per-fiber table) |
| FIBER | int32 | Fiber number, 0-4999 across the whole focal plane (not per-camera like cframe's FIBERMAP) | 0 | `fiberqa_table['FIBER']` (per-fiber table) |
| TARGET_RA | float64 | Target RA (deg) | 215.78365050347062 | `fiberqa_table['TARGET_RA']` (per-fiber table) |
| TARGET_DEC | float64 | Target Dec (deg) | -10.155565978245603 | `fiberqa_table['TARGET_DEC']` (per-fiber table) |
| FIBER_X | float64 | Fiber X position (post-correction) | 81.61396925999655 | `fiberqa_table['FIBER_X']` (per-fiber table) |
| FIBER_Y | float64 | Fiber Y position (post-correction) | -286.1526430867038 | `fiberqa_table['FIBER_Y']` (per-fiber table) |
| DELTA_X | float64 | Positioning residual, X | -0.003969259996546684 | `fiberqa_table['DELTA_X']` (per-fiber table) |
| DELTA_Y | float64 | Positioning residual, Y | 0.0006430867037716715 | `fiberqa_table['DELTA_Y']` (per-fiber table) |
| EBV | float32 | Galactic extinction E(B-V) at this target | 0.06676148 | `fiberqa_table['EBV']` (per-fiber table) |
| QAFIBERSTATUS | int32 | Per-fiber QA status bitmask (0 = good) -- this is the per-fiber detail behind the exposure-level NGOODFIB/NGOODPET summary | 0 | `fiberqa_table['QAFIBERSTATUS']` (per-fiber table) |
| EFFTIME_SPEC | float32 | Per-fiber effective spectroscopic time (s) -- finer-grained than the whole-exposure EFFTIME in the FIBERQA header | 187.63637 | `fiberqa_table['EFFTIME_SPEC']` (per-fiber table) |


## Offline per-exposure QA: `exposure-qa-<expid>.fits` -- `PETALQA` table

10 rows (one per petal). Available as `Exposure.petalqa` (DataFrame indexed by PETAL_LOC). Most columns (NGOODPOS/NGOODFIB/NSTDSTAR/WORSTREADNOISE/STARRMS/NCFRAME and the per-petal sky/throughput RMS+chi2 columns) are genuinely new detail not available elsewhere in this project; the TSNR2_*/SKY_MAG_*_SPEC columns duplicate exposure-level totals already in `redux_row`/`exposures-daily.csv` (same metric, summed across petals) -- prefer those for the whole-exposure number.

| Field | Type | Description | Example value | Source |
|---|---|---|---|---|
| PETAL_LOC | int16 | Petal (spectrograph unit) number 0-9 | 0 | `petalqa['PETAL_LOC']` (per-petal table) |
| WORSTREADNOISE | float32 | Worst (highest) CCD read noise across this petal's cameras | 2.8247197 | `petalqa['WORSTREADNOISE']` (per-petal table) |
| NGOODPOS | int16 | Number of fiber positioners passing QA on this petal | 471 | `petalqa['NGOODPOS']` (per-petal table) |
| NGOODFIB | int16 | Number of fibers passing QA on this petal -- per-petal detail behind the exposure-level FIBERQA NGOODFIB total | 464 | `petalqa['NGOODFIB']` (per-petal table) |
| NSTDSTAR | int16 | Number of standard stars used for flux calibration on this petal | 10 | `petalqa['NSTDSTAR']` (per-petal table) |
| STARRMS | float32 | RMS scatter of standard-star flux calibration residuals on this petal | 0.05494451 | `petalqa['STARRMS']` (per-petal table) |
| EFFTIME_SPEC | float32 | Effective spectroscopic time for this petal (s) | 209.53212 | `petalqa['EFFTIME_SPEC']` (per-petal table) |
| NCFRAME | int16 | Number of cframes (exposure sequence coadds) combined for this petal | 3 | `petalqa['NCFRAME']` (per-petal table) |
| BSKYTHRURMS | float32 | Sky-fiber throughput RMS, b camera | 0.009978867 | `petalqa['BSKYTHRURMS']` (per-petal table) |
| BSKYCHI2PDF | float32 | Sky-subtraction chi^2/dof, b camera | 0.9343856 | `petalqa['BSKYCHI2PDF']` (per-petal table) |
| RSKYTHRURMS | float32 | Sky-fiber throughput RMS, r camera | 0.005598954 | `petalqa['RSKYTHRURMS']` (per-petal table) |
| RSKYCHI2PDF | float32 | Sky-subtraction chi^2/dof, r camera | 0.97836775 | `petalqa['RSKYCHI2PDF']` (per-petal table) |
| ZSKYTHRURMS | float32 | Sky-fiber throughput RMS, z camera | 0.00379174 | `petalqa['ZSKYTHRURMS']` (per-petal table) |
| ZSKYCHI2PDF | float32 | Sky-subtraction chi^2/dof, z camera | 0.99931043 | `petalqa['ZSKYCHI2PDF']` (per-petal table) |
| BTHRUFRAC | float32 | Median throughput fraction, b camera | 0.9286643 | `petalqa['BTHRUFRAC']` (per-petal table) |
| RTHRUFRAC | float32 | Median throughput fraction, r camera | 0.9248428 | `petalqa['RTHRUFRAC']` (per-petal table) |
| ZTHRUFRAC | float32 | Median throughput fraction, z camera | 0.9592113 | `petalqa['ZTHRUFRAC']` (per-petal table) |
| SKY_MAG_G_SPEC | float32 | Per-petal sky brightness, g band, AB mag/arcsec^2 (distinct from FIBERQA's whole-exposure SKY_MAG_G_SPEC) | 21.527739 | `petalqa['SKY_MAG_G_SPEC']` (per-petal table) |
| SKY_MAG_R_SPEC | float32 | Per-petal sky brightness, r band | 20.841593 | `petalqa['SKY_MAG_R_SPEC']` (per-petal table) |
| SKY_MAG_Z_SPEC | float32 | Per-petal sky brightness, z band | 19.031895 | `petalqa['SKY_MAG_Z_SPEC']` (per-petal table) |
| TSNR2_ELG_B | float32 | Per-petal ELG template S/N^2, B camera -- same metric as the whole-exposure TSNR2_ELG total in redux_row/exposures-daily.csv, but per petal rather than summed | 0.018429253 | `petalqa['TSNR2_ELG_B']` (per-petal table) |
| TSNR2_ELG_R | float32 | Per-petal ELG template S/N^2, R camera -- same metric as the whole-exposure TSNR2_ELG total in redux_row/exposures-daily.csv, but per petal rather than summed | 4.990127 | `petalqa['TSNR2_ELG_R']` (per-petal table) |
| TSNR2_ELG_Z | float32 | Per-petal ELG template S/N^2, Z camera -- same metric as the whole-exposure TSNR2_ELG total in redux_row/exposures-daily.csv, but per petal rather than summed | 19.011303 | `petalqa['TSNR2_ELG_Z']` (per-petal table) |
| TSNR2_QSO_B | float32 | Per-petal QSO template S/N^2, B camera -- same metric as the whole-exposure TSNR2_QSO total in redux_row/exposures-daily.csv, but per petal rather than summed | 0.41313574 | `petalqa['TSNR2_QSO_B']` (per-petal table) |
| TSNR2_QSO_R | float32 | Per-petal QSO template S/N^2, R camera -- same metric as the whole-exposure TSNR2_QSO total in redux_row/exposures-daily.csv, but per petal rather than summed | 1.320497 | `petalqa['TSNR2_QSO_R']` (per-petal table) |
| TSNR2_QSO_Z | float32 | Per-petal QSO template S/N^2, Z camera -- same metric as the whole-exposure TSNR2_QSO total in redux_row/exposures-daily.csv, but per petal rather than summed | 3.21221 | `petalqa['TSNR2_QSO_Z']` (per-petal table) |
| TSNR2_LRG_B | float32 | Per-petal LRG template S/N^2, B camera -- same metric as the whole-exposure TSNR2_LRG total in redux_row/exposures-daily.csv, but per petal rather than summed | 0.1866554 | `petalqa['TSNR2_LRG_B']` (per-petal table) |
| TSNR2_LRG_R | float32 | Per-petal LRG template S/N^2, R camera -- same metric as the whole-exposure TSNR2_LRG total in redux_row/exposures-daily.csv, but per petal rather than summed | 7.685456 | `petalqa['TSNR2_LRG_R']` (per-petal table) |
| TSNR2_LRG_Z | float32 | Per-petal LRG template S/N^2, Z camera -- same metric as the whole-exposure TSNR2_LRG total in redux_row/exposures-daily.csv, but per petal rather than summed | 8.902827 | `petalqa['TSNR2_LRG_Z']` (per-petal table) |
| TSNR2_LYA_B | float32 | Per-petal LYA template S/N^2, B camera -- same metric as the whole-exposure TSNR2_LYA total in redux_row/exposures-daily.csv, but per petal rather than summed | 12.305319 | `petalqa['TSNR2_LYA_B']` (per-petal table) |
| TSNR2_LYA_R | float32 | Per-petal LYA template S/N^2, R camera -- same metric as the whole-exposure TSNR2_LYA total in redux_row/exposures-daily.csv, but per petal rather than summed | 0.008186403 | `petalqa['TSNR2_LYA_R']` (per-petal table) |
| TSNR2_LYA_Z | float32 | Per-petal LYA template S/N^2, Z camera -- same metric as the whole-exposure TSNR2_LYA total in redux_row/exposures-daily.csv, but per petal rather than summed | 0.0 | `petalqa['TSNR2_LYA_Z']` (per-petal table) |
| TSNR2_BGS_B | float32 | Per-petal BGS template S/N^2, B camera -- same metric as the whole-exposure TSNR2_BGS total in redux_row/exposures-daily.csv, but per petal rather than summed | 107.7736 | `petalqa['TSNR2_BGS_B']` (per-petal table) |
| TSNR2_BGS_R | float32 | Per-petal BGS template S/N^2, R camera -- same metric as the whole-exposure TSNR2_BGS total in redux_row/exposures-daily.csv, but per petal rather than summed | 542.7214 | `petalqa['TSNR2_BGS_R']` (per-petal table) |
| TSNR2_BGS_Z | float32 | Per-petal BGS template S/N^2, Z camera -- same metric as the whole-exposure TSNR2_BGS total in redux_row/exposures-daily.csv, but per petal rather than summed | 852.78046 | `petalqa['TSNR2_BGS_Z']` (per-petal table) |
| TSNR2_GPBDARK_B | float32 | Per-petal GPBDARK template S/N^2, B camera -- same metric as the whole-exposure TSNR2_GPBDARK total in redux_row/exposures-daily.csv, but per petal rather than summed | 37.643417 | `petalqa['TSNR2_GPBDARK_B']` (per-petal table) |
| TSNR2_GPBDARK_R | float32 | Per-petal GPBDARK template S/N^2, R camera -- same metric as the whole-exposure TSNR2_GPBDARK total in redux_row/exposures-daily.csv, but per petal rather than summed | 2409.9316 | `petalqa['TSNR2_GPBDARK_R']` (per-petal table) |
| TSNR2_GPBDARK_Z | float32 | Per-petal GPBDARK template S/N^2, Z camera -- same metric as the whole-exposure TSNR2_GPBDARK total in redux_row/exposures-daily.csv, but per petal rather than summed | 3.626135e-06 | `petalqa['TSNR2_GPBDARK_Z']` (per-petal table) |
| TSNR2_GPBBRIGHT_B | float32 | Per-petal GPBBRIGHT template S/N^2, B camera -- same metric as the whole-exposure TSNR2_GPBBRIGHT total in redux_row/exposures-daily.csv, but per petal rather than summed | 7.40951 | `petalqa['TSNR2_GPBBRIGHT_B']` (per-petal table) |
| TSNR2_GPBBRIGHT_R | float32 | Per-petal GPBBRIGHT template S/N^2, R camera -- same metric as the whole-exposure TSNR2_GPBBRIGHT total in redux_row/exposures-daily.csv, but per petal rather than summed | 468.2792 | `petalqa['TSNR2_GPBBRIGHT_R']` (per-petal table) |
| TSNR2_GPBBRIGHT_Z | float32 | Per-petal GPBBRIGHT template S/N^2, Z camera -- same metric as the whole-exposure TSNR2_GPBBRIGHT total in redux_row/exposures-daily.csv, but per petal rather than summed | 7.1993264e-07 | `petalqa['TSNR2_GPBBRIGHT_Z']` (per-petal table) |
| TSNR2_GPBBACKUP_B | float32 | Per-petal GPBBACKUP template S/N^2, B camera -- same metric as the whole-exposure TSNR2_GPBBACKUP total in redux_row/exposures-daily.csv, but per petal rather than summed | 66.14333 | `petalqa['TSNR2_GPBBACKUP_B']` (per-petal table) |
| TSNR2_GPBBACKUP_R | float32 | Per-petal GPBBACKUP template S/N^2, R camera -- same metric as the whole-exposure TSNR2_GPBBACKUP total in redux_row/exposures-daily.csv, but per petal rather than summed | 3832.7527 | `petalqa['TSNR2_GPBBACKUP_R']` (per-petal table) |
| TSNR2_GPBBACKUP_Z | float32 | Per-petal GPBBACKUP template S/N^2, Z camera -- same metric as the whole-exposure TSNR2_GPBBACKUP total in redux_row/exposures-daily.csv, but per petal rather than summed | 6.0208554e-06 | `petalqa['TSNR2_GPBBACKUP_Z']` (per-petal table) |


## Offline per-exposure QA: `calibstars-<expid>.csv` -- standard-star flux calibration table

142 rows (one per spectrophotometric standard star used for flux calibration). Available as `Exposure.calibstars` (DataFrame indexed by FIBER). FIBER is the whole-focal-plane 0-4999 numbering (same as cframe_table/fiberqa_table's FIBER column) -- `FIBER // 500 == PETAL_LOC` always holds, but DEVICE_LOC has no formula and needs a join against `fiberqa_table`/`cframe_table` (both already carry FIBER alongside the (PETAL_LOC, DEVICE_LOC) index). Also available under other specprods (e.g. `redux_release='matterhorn'`), same directory/naming convention as cframe.

| Field | Type | Description | Example value | Source |
|---|---|---|---|---|
| FIBER | int64 | Whole-focal-plane fiber number, 0-4999 -- same numbering as cframe_table/fiberqa_table's FIBER column, but NOT the (PETAL_LOC, DEVICE_LOC) index used elsewhere in this project (FIBER // 500 == PETAL_LOC always holds; DEVICE_LOC has no formula and needs a join against fiberqa_table/cframe_table) | 12 | `calibstars['FIBER']` (per-star table, indexed by FIBER) |
| RCALIBFRAC | float64 | Ratio of r-band spectroscopic flux to model flux for this standard star (confirmed via the official DESI datamodel docs) | 0.8897678498382974 | `calibstars['RCALIBFRAC']` (per-star table, indexed by FIBER) |
| EBV | float64 | Galactic extinction E(B-V) reddening from SFD98 | 0.0600866414606571 | `calibstars['EBV']` (per-star table, indexed by FIBER) |
| MODEL_COLOR | float64 | G-R color of the best-fit model for this star | 0.3126283307491269 | `calibstars['MODEL_COLOR']` (per-star table, indexed by FIBER) |
| DATA_COLOR | float64 | G-R color measured from the data for this star | 0.3331871032714844 | `calibstars['DATA_COLOR']` (per-star table, indexed by FIBER) |
| X | float64 | Focal-plane X position (mm) | -4.509812831878662 | `calibstars['X']` (per-star table, indexed by FIBER) |
| Y | float64 | Focal-plane Y position (mm) | -228.1053924560547 | `calibstars['Y']` (per-star table, indexed by FIBER) |
| VALID | float64 | Whether this standard star was selected as good (1) for the flux calibration fit -- rejected (0) if a 3-sigma RCALIBFRAC outlier across petals, or if its G-R color differs from the model by more than 0.2*EBV | 1.0 | `calibstars['VALID']` (per-star table, indexed by FIBER) |


## Exposure directory: `fiberassign-<tileid>.fits.gz` -- `FIBERASSIGN` extension

5000 rows -- one per fiber across the **whole focal plane** (not per-petal like cframe's 500-row FIBERMAP). Available as `Exposure.fiberassign_table` (DataFrame indexed by (PETAL_LOC, DEVICE_LOC)). Carries the same targeting bitmasks as cframe's FIBERMAP (DESI_TARGET/BGS_TARGET/MWS_TARGET/SCND_TARGET) but in a single fast read -- confirmed ~60x faster than looping `cframe_table` over every petal for the same columns (~0.14s vs. ~9s per exposure).

| Field | Type | Description | Example value | Source |
|---|---|---|---|---|
| TARGETID | int64 | Unique target identifier | 48423634854746143 | `fiberassign_table['TARGETID']` (per-fiber table) |
| PETAL_LOC | int16 | Petal (spectrograph unit) number 0-9 | 0 | `fiberassign_table['PETAL_LOC']` (per-fiber table) |
| DEVICE_LOC | int32 | Positioner device location within the petal | 311 | `fiberassign_table['DEVICE_LOC']` (per-fiber table) |
| LOCATION | int32 | PETAL_LOC*1000+DEVICE_LOC | 311 | `fiberassign_table['LOCATION']` (per-fiber table) |
| FIBER | int32 | Fiber number, 0-4999 across the whole focal plane -- same numbering as cframe_table/fiberqa_table/calibstars's FIBER | 0 | `fiberassign_table['FIBER']` (per-fiber table) |
| FIBERSTATUS | int32 |  | 0 | `fiberassign_table['FIBERSTATUS']` (per-fiber table) |
| TARGET_RA | float64 | Target RA (deg) | 215.78365050347062 | `fiberassign_table['TARGET_RA']` (per-fiber table) |
| TARGET_DEC | float64 | Target Dec (deg) | -10.155565978245603 | `fiberassign_table['TARGET_DEC']` (per-fiber table) |
| PMRA | float32 |  | 0.0 | `fiberassign_table['PMRA']` (per-fiber table) |
| PMDEC | float32 |  | 0.0 | `fiberassign_table['PMDEC']` (per-fiber table) |
| REF_EPOCH | float32 |  | 2015.5 | `fiberassign_table['REF_EPOCH']` (per-fiber table) |
| LAMBDA_REF | float32 |  | 5400.0 | `fiberassign_table['LAMBDA_REF']` (per-fiber table) |
| FA_TARGET | int64 | Raw fiberassign target bitmask used at assignment time | 1152921504606846976 | `fiberassign_table['FA_TARGET']` (per-fiber table) |
| FA_TYPE | uint8 |  | 1 | `fiberassign_table['FA_TYPE']` (per-fiber table) |
| OBJTYPE | <U3 |  | TGT | `fiberassign_table['OBJTYPE']` (per-fiber table) |
| FIBERASSIGN_X | float32 |  | 81.61246 | `fiberassign_table['FIBERASSIGN_X']` (per-fiber table) |
| FIBERASSIGN_Y | float32 |  | -286.1761 | `fiberassign_table['FIBERASSIGN_Y']` (per-fiber table) |
| PRIORITY | int32 |  | 2000 | `fiberassign_table['PRIORITY']` (per-fiber table) |
| SUBPRIORITY | float64 |  | 0.7354495758341314 | `fiberassign_table['SUBPRIORITY']` (per-fiber table) |
| OBSCONDITIONS | int32 |  | 516 | `fiberassign_table['OBSCONDITIONS']` (per-fiber table) |
| MTL_HIGHEST | int32 |  | 4 | `fiberassign_table['MTL_HIGHEST']` (per-fiber table) |
| MTL_WANTED | int32 |  | 4 | `fiberassign_table['MTL_WANTED']` (per-fiber table) |
| MTL_CONTAINS | int32 |  | 4 | `fiberassign_table['MTL_CONTAINS']` (per-fiber table) |
| RELEASE | int16 |  | 11010 | `fiberassign_table['RELEASE']` (per-fiber table) |
| BRICKNAME | <U8 |  | 2156m102 | `fiberassign_table['BRICKNAME']` (per-fiber table) |
| BRICKID | int32 |  | 272457 | `fiberassign_table['BRICKID']` (per-fiber table) |
| BRICK_OBJID | int32 |  | 6175 | `fiberassign_table['BRICK_OBJID']` (per-fiber table) |
| MORPHTYPE | <U3 |  | SER | `fiberassign_table['MORPHTYPE']` (per-fiber table) |
| EBV | float32 |  | 0.06676148 | `fiberassign_table['EBV']` (per-fiber table) |
| FLUX_G | float32 |  | 2.570513 | `fiberassign_table['FLUX_G']` (per-fiber table) |
| FLUX_R | float32 |  | 8.596681 | `fiberassign_table['FLUX_R']` (per-fiber table) |
| FLUX_Z | float32 |  | 19.957739 | `fiberassign_table['FLUX_Z']` (per-fiber table) |
| FLUX_W1 | float32 |  | 35.844257 | `fiberassign_table['FLUX_W1']` (per-fiber table) |
| FLUX_W2 | float32 |  | 20.74107 | `fiberassign_table['FLUX_W2']` (per-fiber table) |
| FLUX_IVAR_G | float32 |  | 408.1576 | `fiberassign_table['FLUX_IVAR_G']` (per-fiber table) |
| FLUX_IVAR_R | float32 |  | 171.55586 | `fiberassign_table['FLUX_IVAR_R']` (per-fiber table) |
| FLUX_IVAR_Z | float32 |  | 29.047504 | `fiberassign_table['FLUX_IVAR_Z']` (per-fiber table) |
| FLUX_IVAR_W1 | float32 |  | 3.1144295 | `fiberassign_table['FLUX_IVAR_W1']` (per-fiber table) |
| FLUX_IVAR_W2 | float32 |  | 0.6790512 | `fiberassign_table['FLUX_IVAR_W2']` (per-fiber table) |
| FIBERFLUX_G | float32 |  | 0.67957896 | `fiberassign_table['FIBERFLUX_G']` (per-fiber table) |
| FIBERFLUX_R | float32 |  | 2.272746 | `fiberassign_table['FIBERFLUX_R']` (per-fiber table) |
| FIBERFLUX_Z | float32 |  | 5.2763243 | `fiberassign_table['FIBERFLUX_Z']` (per-fiber table) |
| FIBERTOTFLUX_G | float32 |  | 0.6845836 | `fiberassign_table['FIBERTOTFLUX_G']` (per-fiber table) |
| FIBERTOTFLUX_R | float32 |  | 2.2859528 | `fiberassign_table['FIBERTOTFLUX_R']` (per-fiber table) |
| FIBERTOTFLUX_Z | float32 |  | 5.4116664 | `fiberassign_table['FIBERTOTFLUX_Z']` (per-fiber table) |
| MASKBITS | int16 |  | 0 | `fiberassign_table['MASKBITS']` (per-fiber table) |
| SERSIC | float32 |  | 0.5 | `fiberassign_table['SERSIC']` (per-fiber table) |
| SHAPE_R | float32 |  | 1.3703187 | `fiberassign_table['SHAPE_R']` (per-fiber table) |
| SHAPE_E1 | float32 |  | 0.3320448 | `fiberassign_table['SHAPE_E1']` (per-fiber table) |
| SHAPE_E2 | float32 |  | -0.058419313 | `fiberassign_table['SHAPE_E2']` (per-fiber table) |
| REF_ID | int64 |  | 0 | `fiberassign_table['REF_ID']` (per-fiber table) |
| REF_CAT | <U0 |  |  | `fiberassign_table['REF_CAT']` (per-fiber table) |
| GAIA_PHOT_G_MEAN_MAG | float32 |  | 0.0 | `fiberassign_table['GAIA_PHOT_G_MEAN_MAG']` (per-fiber table) |
| GAIA_PHOT_BP_MEAN_MAG | float32 |  | 0.0 | `fiberassign_table['GAIA_PHOT_BP_MEAN_MAG']` (per-fiber table) |
| GAIA_PHOT_RP_MEAN_MAG | float32 |  | 0.0 | `fiberassign_table['GAIA_PHOT_RP_MEAN_MAG']` (per-fiber table) |
| PARALLAX | float32 |  | 0.0 | `fiberassign_table['PARALLAX']` (per-fiber table) |
| PHOTSYS | <U1 |  | S | `fiberassign_table['PHOTSYS']` (per-fiber table) |
| PRIORITY_INIT | int64 |  | 2000 | `fiberassign_table['PRIORITY_INIT']` (per-fiber table) |
| NUMOBS_INIT | int64 |  | 2 | `fiberassign_table['NUMOBS_INIT']` (per-fiber table) |
| DESI_TARGET | int64 | Targeting bitmask, main DARK/BRIGHT survey -- includes STD_FAINT/STD_WD/STD_BRIGHT standard-star bits | 1152921504606846976 | `fiberassign_table['DESI_TARGET']` (per-fiber table) |
| BGS_TARGET | int64 | BGS-specific targeting bitmask | 65537 | `fiberassign_table['BGS_TARGET']` (per-fiber table) |
| MWS_TARGET | int64 | MWS-specific targeting bitmask -- also where BACKUP-program exposures (program='BACKUP') flag their standard stars (GAIA_STD_FAINT/GAIA_STD_WD/GAIA_STD_BRIGHT) instead of DESI_TARGET -- confirmed real, not hypothetical (see notebooks/calibstars_linphi.ipynb) | 0 | `fiberassign_table['MWS_TARGET']` (per-fiber table) |
| SCND_TARGET | int64 | Secondary-program targeting bitmask | 0 | `fiberassign_table['SCND_TARGET']` (per-fiber table) |
| PLATE_RA | float64 |  | 215.78365050347062 | `fiberassign_table['PLATE_RA']` (per-fiber table) |
| PLATE_DEC | float64 |  | -10.155565978245603 | `fiberassign_table['PLATE_DEC']` (per-fiber table) |

<!-- BEGIN telemetry appendix (generated by scripts/build_telemetry_appendix.py) -->

## Appendix: additional telemetry tables

The main glossary above covers only the telemetry tables `telemetry_mining` integrates directly. This appendix is a broader **reference listing of column names** for other `telemetry`-schema tables that may be useful in future studies. It is deliberately **not hand-annotated** -- a column's name, its SQL type, and one sampled value are usually enough to tell what the quantity is.

It is generated, not hand-typed: `scripts/collect_telemetry_columns.py` lists the columns via `information_schema` against the live DB (see the "explore a telemetry table" note near the top of this file), and `scripts/build_telemetry_appendix.py` formats them here. To refresh or extend it, edit the table list in the collector, rerun it where the DB is reachable, and rerun the builder.

Reach any column the same way as the integrated telemetry tables: `exp.telemetry('<table>', columns=['<col>'])` for the rows within an exposure's time window, or `telemetry_mining.db.fetch_df(Config.default(), "SELECT ... FROM telemetry.<table> ...")` for an arbitrary query.

*86 tables, 1948 columns (DB snapshot 2026-07-27). Example values are from a single sampled row; a blank means that column was NULL in the sampled row.*

Omitted here because they are already documented in full above: `environmentmonitor_telescope`, `environmentmonitor_tower`, `guider_centroids`, `environmentmonitor_dust`.

| Telemetry variable | Table | Columns |
|---|---|---|
| `TELEMETRY_LIMITS` | [`telemetry_limits`](#telemetry_limits) | 15 |
| `GFA_TELEMETRY` | [`gfa_telemetry`](#gfa_telemetry) | 24 |
| `GFA_STATUS` | [`gfa_status`](#gfa_status) | 17 |
| `CALIBRATION_TELEMETRY` | [`calibration_telemetry`](#calibration_telemetry) | 54 |
| `PC_TELEMETRY` | [`pc_telemetry`](#pc_telemetry) | 24 |
| `PC_TELEMETRY-CAN-FID` | [`pc_telemetry_can_fid`](#pc_telemetry_can_fid) | 19 |
| `PC_TELEMETRY-CAN-ALL` | [`pc_telemetry_can_all`](#pc_telemetry_can_all) | 23 |
| `PC_TELEMETRY-STATUS` | [`pc_telemetry_status`](#pc_telemetry_status) | 27 |
| `PBPOWER_PBOUTLETS` | [`pbpower_pboutlets`](#pbpower_pboutlets) | 16 |
| `PBPOWER_FXC` | [`pbpower_fxc`](#pbpower_fxc) | 7 |
| `ETC_TELEMETRY` | [`etc_telemetry`](#etc_telemetry) | 65 |
| `FVC_CAMERASTATUS` | [`fvc_camerastatus`](#fvc_camerastatus) | 15 |
| `OCS_POSITIONING` | [`ocs_positioning`](#ocs_positioning) | 39 |
| `ENVIRONMENTMONITOR_DOME` | [`environmentmonitor_dome`](#environmentmonitor_dome) | 59 |
| `ENVIRONMENTMONITOR_UPS` | [`environmentmonitor_ups`](#environmentmonitor_ups) | 36 |
| `ENVIRONMENTMONITOR_COMPUTER` | [`environmentmonitor_computer`](#environmentmonitor_computer) | 14 |
| `TCS_INFO` | [`tcs_info`](#tcs_info) | 59 |
| `OCS_OBSINFO` | [`ocs_obsinfo`](#ocs_obsinfo) | 10 |
| `SKYCAM_TELEMETRY` | [`skycam_telemetry`](#skycam_telemetry) | 17 |
| `OCS_GFADATA` | [`ocs_gfadata`](#ocs_gfadata) | 42 |
| `SKY_SKYLEVEL` | [`sky_skylevel`](#sky_skylevel) | 9 |
| `LUT_CONFIGURATION` | [`lut_configuration`](#lut_configuration) | 12 |
| `LUT_LOOKUP` | [`lut_lookup`](#lut_lookup) | 16 |
| `ETC_SEEING` | [`etc_seeing`](#etc_seeing) | 8 |
| `ETC_SKYLEVEL` | [`etc_skylevel`](#etc_skylevel) | 8 |
| `ETC_REQUESTS` | [`etc_requests`](#etc_requests) | 10 |
| `ETC_TRANSPARENCY` | [`etc_transparency`](#etc_transparency) | 8 |
| `PERFORMANCE_NIGHT` | [`performance_night`](#performance_night) | 13 |
| `PERFORMANCE_CURRENT` | [`performance_current`](#performance_current) | 59 |
| `PC_PTL-STATUS` | [`pc_ptl_status`](#pc_ptl_status) | 28 |
| `PC_PTL-SENSORS` | [`pc_ptl_sensors`](#pc_ptl_sensors) | 43 |
| `PC_PTL-POWERUP` | [`pc_ptl_powerup`](#pc_ptl_powerup) | 14 |
| `PC_PTL-TEMPS` | [`pc_ptl_temps`](#pc_ptl_temps) | 31 |
| `HEXAPOD_ROTATOR` | [`hexapod_rotator`](#hexapod_rotator) | 16 |
| `ENVIRONMENTMONITOR_FPE` | [`environmentmonitor_fpe`](#environmentmonitor_fpe) | 31 |
| `FXC_ADCS` | [`fxc_adcs`](#fxc_adcs) | 13 |
| `FXC_CHILLER` | [`fxc_chiller`](#fxc_chiller) | 24 |
| `FXC_TEMPS` | [`fxc_temps`](#fxc_temps) | 16 |
| `FXC_PID` | [`fxc_pid`](#fxc_pid) | 17 |
| `PERFORMANCE_ACCUMULATED` | [`performance_accumulated`](#performance_accumulated) | 60 |
| `FXC_MISC` | [`fxc_misc`](#fxc_misc) | 32 |
| `FXC_VAISALA` | [`fxc_vaisala`](#fxc_vaisala) | 21 |
| `FXC_THR` | [`fxc_thr`](#fxc_thr) | 23 |
| `FXC_INTERLOCKS` | [`fxc_interlocks`](#fxc_interlocks) | 13 |
| `FXC_FANS` | [`fxc_fans`](#fxc_fans) | 50 |
| `AOS_LATEST` | [`aos_latest`](#aos_latest) | 39 |
| `AOS_AVERAGE` | [`aos_average`](#aos_average) | 41 |
| `ADC_CONTROLLERS` | [`adc_controllers`](#adc_controllers) | 19 |
| `HEXAPOD_POS` | [`hexapod_pos`](#hexapod_pos) | 8 |
| `DONUT_SUMMARY` | [`donut_summary`](#donut_summary) | 83 |
| `HEXAPOD_TRIM` | [`hexapod_trim`](#hexapod_trim) | 8 |
| `HEXAPOD_HCUSTATUS` | [`hexapod_hcustatus`](#hexapod_hcustatus) | 7 |
| `ICS_TIMING` | [`ics_timing`](#ics_timing) | 30 |
| `GFA_BOOTTIME` | [`gfa_boottime`](#gfa_boottime) | 8 |
| `CRYOSTAT_TELEMETRY` | [`cryostat_telemetry`](#cryostat_telemetry) | 64 |
| `SPECTROGRAPHS_CCDS` | [`spectrographs_ccds`](#spectrographs_ccds) | 18 |
| `SPECTROGRAPHS_SENSORS` | [`spectrographs_sensors`](#spectrographs_sensors) | 18 |
| `SPECTROGRAPHS_MECHANISMS` | [`spectrographs_mechanisms`](#spectrographs_mechanisms) | 21 |
| `CALIBRATION_TESTSLIT` | [`calibration_testslit`](#calibration_testslit) | 16 |
| `SHACK_SHACK` | [`shack_shack`](#shack_shack) | 24 |
| `SHACK_WEC` | [`shack_wec`](#shack_wec) | 20 |
| `SHACK_WAGO` | [`shack_wago`](#shack_wago) | 10 |
| `PERFORMANCE_MONITOR` | [`performance_monitor`](#performance_monitor) | 9 |
| `CIFIDS_TEMPERATURES` | [`cifids_temperatures`](#cifids_temperatures) | 11 |
| `ICS_MEMORY` | [`ics_memory`](#ics_memory) | 10 |
| `CONTMONFP_TELEMETRY` | [`contmonfp_telemetry`](#contmonfp_telemetry) | 9 |
| `FIBER_ANALYSIS` | [`fiber_analysis`](#fiber_analysis) | 43 |
| `GUIDER_SUMMARY` | [`guider_summary`](#guider_summary) | 17 |
| `ENVIRONMENTMONITOR_ELNINO` | [`environmentmonitor_elnino`](#environmentmonitor_elnino) | 14 |
| `PETALMAN_TIMES` | [`petalman_times`](#petalman_times) | 14 |
| `OCS_SLEW` | [`ocs_slew`](#ocs_slew) | 9 |
| `OCS_INTEXPTIME` | [`ocs_intexptime`](#ocs_intexptime) | 7 |
| `GFA_PTL-SENSORS` | [`gfa_ptl_sensors`](#gfa_ptl_sensors) | 32 |
| `GFA_PTL-STATUS` | [`gfa_ptl_status`](#gfa_ptl_status) | 19 |
| `GFA_PTL-POWERUP` | [`gfa_ptl_powerup`](#gfa_ptl_powerup) | 12 |
| `OCS_ASTROMETRY` | [`ocs_astrometry`](#ocs_astrometry) | 18 |
| `SPOTTRACK_CAMERASTATUS` | [`spottrack_camerastatus`](#spottrack_camerastatus) | 27 |
| `FRONTILLUMINATOR_FIOUTLETS` | [`frontilluminator_fioutlets`](#frontilluminator_fioutlets) | 8 |
| `LUX_TELEMETRY` | [`lux_telemetry`](#lux_telemetry) | 8 |
| `NFS_REQUESTTIME` | [`nfs_requesttime`](#nfs_requesttime) | 9 |
| `SPECTROGRAPHS_CPULOAD` | [`spectrographs_cpuload`](#spectrographs_cpuload) | 12 |
| `OCS_NFSCONSTRAINTS` | [`ocs_nfsconstraints`](#ocs_nfsconstraints) | 10 |
| `SPECTROGRAPHS_ACTUATORS` | [`spectrographs_actuators`](#spectrographs_actuators) | 33 |
| `CALIBRATION_CALPDUSWITCH` | [`calibration_calpduswitch`](#calibration_calpduswitch) | 8 |
| `CALIBRATION_BOOTED` | [`calibration_booted`](#calibration_booted) | 7 |
| `PC_PTLTCAN` | [`pc_ptltcan`](#pc_ptltcan) | 11 |

### telemetry_limits

Shared variable `TELEMETRY_LIMITS`.

| Field | Type | Example |
|---|---|---|
| telemetry_limits | integer | 195692 |
| shared_variable | text | SPECTROGRAPHS_SENSORS |
| value | text | bench_coll_temp |
| warning_limits | ARRAY | [None, 30.0] |
| alert_limits | ARRAY | [None, 35.0] |
| unit_field_name | text | unit |
| unit | text | 1 |
| subunit_field_name | text |  |
| subunit | text |  |
| time_recorded | timestamp with time zone | 2020-01-06 00:59:19.809283+00:00 |
| dos_instance | text | extern |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2020-01-06 00:59:19.810377+00:00 |
| row_status_user | text | desi_writer |
| searchable_columns | jsonb |  |

### gfa_telemetry

Shared variable `GFA_TELEMETRY`.

| Field | Type | Example |
|---|---|---|
| gfa_telemetry | integer | 1 |
| last_updated | text | 2019-08-16T04:08:29.588340 |
| status | text | READY |
| ccdpower | double precision | 0.865 |
| ambient | double precision | 0.449 |
| unit | integer | 900 |
| role | text | GUIDE900 |
| settemp | double precision | 0.049 |
| time_recorded | timestamp with time zone | 2019-08-16 04:08:29.593808+00:00 |
| dos_instance | text | extern |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2019-08-16 04:08:29.594265+00:00 |
| row_status_user | text | desi_writer |
| ccdtemp | double precision |  |
| cooling | integer |  |
| hotpeltier | double precision |  |
| coldpeltier | double precision |  |
| filter | double precision |  |
| humid2 | double precision |  |
| humid3 | double precision |  |
| fpga | double precision |  |
| camerahumid | double precision |  |
| cameratemp | double precision |  |
| simulated | integer |  |

### gfa_status

Shared variable `GFA_STATUS`.

| Field | Type | Example |
|---|---|---|
| gfa_status | integer | 1 |
| state | text | UNKNOWN |
| bias_enabled | integer |  |
| connected | integer | 0 |
| biased | integer | 0 |
| temp_setpoint | double precision |  |
| last_updated | text | 2019-08-16T04:08:09.558267 |
| unit | integer | 900 |
| role | text | GUIDE900 |
| time_recorded | timestamp with time zone | 2019-08-16 04:08:09.564743+00:00 |
| dos_instance | text | extern |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2019-08-16 04:08:09.565335+00:00 |
| row_status_user | text | desi_writer |
| temp_regulation | ARRAY |  |
| loopmode | integer |  |
| simulated | integer |  |

### calibration_telemetry

Shared variable `CALIBRATION_TELEMETRY`.

| Field | Type | Example |
|---|---|---|
| calibration_telemetry | integer | 1 |
| cal0_temp1 | double precision | 5.4375 |
| cal0_temp2 | double precision | 5.71875 |
| cal0_humidity | double precision | 47.139384 |
| cal0_temp3 | double precision | 5.03125 |
| cal1_temp1 | double precision | 4.96875 |
| cal1_temp2 | double precision | 5.90625 |
| cal1_temp3 | double precision | 5.75 |
| cal1_humidity | double precision | 47.142437 |
| cal2_temp1 | double precision | 5.75 |
| cal2_temp2 | double precision | 5.875 |
| cal2_humidity | double precision | 46.542234 |
| cal2_temp3 | double precision | 5.6875 |
| cal3_temp1 | double precision | 5.90625 |
| cal3_temp2 | double precision | 5.53125 |
| cal3_temp3 | double precision | 5.96875 |
| cal3_humidity | double precision | 39.837247 |
| time_recorded | timestamp with time zone | 2020-03-04 14:55:44.391047+00:00 |
| dos_instance | text | desi_20200302 |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2020-03-04 14:55:44.403596+00:00 |
| row_status_user | text | desi_writer |
| cal0_leds_i | double precision |  |
| cal0_halogenbluefilter_i | double precision |  |
| cal0_halogennofilter_i | double precision |  |
| cal0_cd_i | double precision |  |
| cal0_xe_i | double precision |  |
| cal0_ne_i | double precision |  |
| cal0_kr_i | double precision |  |
| cal0_hgar_i | double precision |  |
| cal1_leds_i | double precision |  |
| cal1_halogenbluefilter_i | double precision |  |
| cal1_halogennofilter_i | double precision |  |
| cal1_cd_i | double precision |  |
| cal1_xe_i | double precision |  |
| cal1_ne_i | double precision |  |
| cal1_kr_i | double precision |  |
| cal1_hgar_i | double precision |  |
| cal2_leds_i | double precision |  |
| cal2_halogenbluefilter_i | double precision |  |
| cal2_halogennofilter_i | double precision |  |
| cal2_cd_i | double precision |  |
| cal2_xe_i | double precision |  |
| cal2_ne_i | double precision |  |
| cal2_kr_i | double precision |  |
| cal2_hgar_i | double precision |  |
| cal3_leds_i | double precision |  |
| cal3_halogenbluefilter_i | double precision |  |
| cal3_halogennofilter_i | double precision |  |
| cal3_cd_i | double precision |  |
| cal3_xe_i | double precision |  |
| cal3_ne_i | double precision |  |
| cal3_kr_i | double precision |  |
| cal3_hgar_i | double precision |  |

### pc_telemetry

Shared variable `PC_TELEMETRY`.

| Field | Type | Example |
|---|---|---|
| pc_telemetry | integer | 1 |
| gfa_fan_in_pwm | double precision |  |
| gfa_fan_out_pwm | double precision |  |
| gfa_fan_in_tach | integer |  |
| gfa_fan_out_tach | integer |  |
| gfatime | timestamp with time zone |  |
| pbox_temp_sensor | double precision | 22.018 |
| gxb_temp_sensor | double precision | 21.401 |
| fpp_temp_sensor_1 | double precision | 21.891 |
| fpp_temp_sensor_2 | double precision | 22.476 |
| fpp_temp_sensor_3 | double precision | 21.582 |
| temptime | timestamp with time zone | 2019-09-22 17:27:09.488194+00:00 |
| gxbcur | double precision | 1.8924 |
| gxbtime | timestamp with time zone | 2019-09-22 17:27:09.488107+00:00 |
| pcid | integer | 900 |
| time_recorded | timestamp with time zone | 2019-09-22 17:27:09.496891+00:00 |
| dos_instance | text | extern |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2019-09-22 17:27:09.497928+00:00 |
| row_status_user | text | desi_writer |
| adc_bb | double precision |  |
| adc_buf | double precision |  |
| adc_gfa | double precision |  |
| adc_fan | double precision |  |

### pc_telemetry_can_fid

Shared variable `PC_TELEMETRY-CAN-FID`.

| Field | Type | Example |
|---|---|---|
| pc_telemetry_can_fid | integer | 32765 |
| posfid_temps_n_above_th | integer | 0 |
| posfid_state | text | okay |
| posfid_instatesince | double precision | 1569237682.3018453 |
| posfid_timelastalarm | double precision | 1569237682.3018453 |
| time | timestamp with time zone | 2019-09-23 12:43:17.181738+00:00 |
| pcid | integer | 901 |
| fid_temps | jsonb | [30.51, 30.51, 30.51, 30.51, 30.51, 30.51, 30.51,... |
| fid_temps_max | double precision | 30.51 |
| fid_temps_quantiles | ARRAY | [30.51, 30.51, 30.51, 30.51, 30.51] |
| temp_threshold | integer | 40 |
| time_recorded | timestamp with time zone | 2019-09-23 12:43:17.183304+00:00 |
| dos_instance | text | extern |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2019-09-23 12:43:17.184363+00:00 |
| row_status_user | text | desi_writer |
| fid_temps_n_above_th | integer |  |
| fid_temps_mean | double precision |  |
| fid_temps_median | double precision |  |

### pc_telemetry_can_all

Shared variable `PC_TELEMETRY-CAN-ALL`.

| Field | Type | Example |
|---|---|---|
| pc_telemetry_can_all | integer | 1 |
| time | timestamp with time zone | 2019-09-22 17:30:32.019301+00:00 |
| pcid | integer | 900 |
| posfid_imons | jsonb | {'9000': {'900000': None, '900001': None, '900002... |
| posfid_temps_n_above_th | integer | 0 |
| posfid_state | text | okay |
| fid_temp_quantiles | ARRAY |  |
| temp_threshold | double precision |  |
| posfid_sysclks | jsonb | {'9000': {'900000': 72, '900001': 72, '900002': 7... |
| posfid_temps_quantiles | ARRAY | [34.781, 34.781, 34.781, 34.781, 34.781] |
| posfid_instatesince | double precision | 1569173431.1526911 |
| posfid_timelastalarm | double precision | 1569173431.1526911 |
| fid_temps | jsonb |  |
| fid_temps_max | double precision |  |
| time_recorded | timestamp with time zone | 2019-09-22 17:30:37.034649+00:00 |
| dos_instance | text | extern |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2019-09-22 17:30:37.035940+00:00 |
| row_status_user | text | desi_writer |
| posfid_temps | jsonb |  |
| posfid_temps_max | double precision |  |
| posfid_temps_mean | double precision |  |
| posfid_temps_median | double precision |  |

### pc_telemetry_status

Shared variable `PC_TELEMETRY-STATUS`.

| Field | Type | Example |
|---|---|---|
| pc_telemetry_status | integer | 17 |
| gfa_ovrtmp | integer | 0 |
| gfa_fan_in_en | integer |  |
| gfa_fan_out_en | integer |  |
| pospwr_ps1_fbk | integer |  |
| pospwr_ps2_fbk | integer |  |
| pospwr_ps1_en | integer |  |
| pospwr_ps2_en | integer |  |
| pcid | integer | 905 |
| gfapwr_en | integer | 0 |
| tec_ctrl | integer | 0 |
| canbrd1_en | integer | 1 |
| canbrd2_en | integer | 1 |
| buff_en1 | integer | 1 |
| buff_en2 | integer | 1 |
| fxc_okay | integer | 1 |
| ccdbiasenabled | integer | 0 |
| ccdbias | integer | 0 |
| telemetryfault | integer |  |
| canbusfault | integer |  |
| time_recorded | timestamp with time zone | 2019-09-22 19:22:02.599055+00:00 |
| dos_instance | text | extern |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2019-09-22 19:22:02.600026+00:00 |
| row_status_user | text | desi_writer |
| status | integer |  |
| time | timestamp with time zone |  |

### pbpower_pboutlets

Shared variable `PBPOWER_PBOUTLETS`.

| Field | Type | Example |
|---|---|---|
| pbpower_pboutlets | integer | 1 |
| petalbox0 | integer | 0 |
| petalbox1 | integer | 0 |
| petalbox2 | integer |  |
| petalbox3 | integer |  |
| petalbox4 | integer |  |
| petalbox5 | integer |  |
| petalbox6 | integer | 0 |
| petalbox7 | integer | 0 |
| petalbox8 | integer | 0 |
| petalbox9 | integer |  |
| time_recorded | timestamp with time zone | 2019-10-21 13:43:36.000545+00:00 |
| dos_instance | text | gfas_20191021 |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2019-10-21 13:43:36.001236+00:00 |
| row_status_user | text | desi_writer |

### pbpower_fxc

Shared variable `PBPOWER_FXC`.

| Field | Type | Example |
|---|---|---|
| pbpower_fxc | integer | 1 |
| fxc | integer |  |
| time_recorded | timestamp with time zone | 2019-10-21 13:43:32.778522+00:00 |
| dos_instance | text | extern |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2019-10-21 13:43:32.778996+00:00 |
| row_status_user | text | desi_writer |

### etc_telemetry

Shared variable `ETC_TELEMETRY`.

| Field | Type | Example |
|---|---|---|
| etc_telemetry | integer | 1 |
| expid | integer |  |
| seeing | double precision | 1.0 |
| transparency | double precision | 0.8 |
| skylevel | double precision | 21.0 |
| time_recorded | timestamp with time zone | 2020-04-22 14:35:59.250512+00:00 |
| dos_instance | text | desisim_20200401 |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2020-04-22 14:35:59.251726+00:00 |
| row_status_user | text | desi_writer |
| simulated | integer |  |
| img_proc | integer |  |
| etc_updated | text |  |
| etc_proc | integer |  |
| etc_ready | integer |  |
| desietc | text |  |
| gfa_count | integer |  |
| sky_count | integer |  |
| desi_count | integer |  |
| signal | double precision |  |
| background | double precision |  |
| efftime | double precision |  |
| realtime | double precision |  |
| efftime_tot | double precision |  |
| realtime_tot | double precision |  |
| remaining | double precision |  |
| proj_efftime | double precision |  |
| next_split | double precision |  |
| splittable | integer |  |
| req_efftime | double precision |  |
| sbprof | text |  |
| max_exptime | double precision |  |
| cosmics_split | double precision |  |
| img_start_time | text |  |
| seeing_updated | text |  |
| ffrac_psf | double precision |  |
| ffrac | double precision |  |
| etc_start_time | text |  |
| skylevel_updated | text |  |
| etc_stop_time | text |  |
| etc_stop_src | text |  |
| about_to_split | integer |  |
| split_requested | integer |  |
| stop_requested | integer |  |
| about_to_finish | integer |  |
| will_not_finish | integer |  |
| ffrac_avg | double precision |  |
| thru_avg | double precision |  |
| transparency_updated | text |  |
| maxsplit | integer |  |
| warning_time | integer |  |
| img_stop_time | text |  |
| img_stop_src | text |  |
| ffrac_elg | double precision |  |
| ffrac_bgs | double precision |  |
| transp | double precision |  |
| speed_dark | double precision |  |
| speed_bright | double precision |  |
| speed_backup | double precision |  |
| speed_dark_nts | double precision |  |
| speed_bright_nts | double precision |  |
| speed_backup_nts | double precision |  |
| rel_rotrate | double precision |  |
| start_time | text |  |
| nts_program | text |  |

### fvc_camerastatus

Shared variable `FVC_CAMERASTATUS`.

| Field | Type | Example |
|---|---|---|
| fvc_camerastatus | integer | 1 |
| controller_open | integer | 1 |
| reset | integer | 1 |
| initialized | integer | 1 |
| shutter_open | integer | 0 |
| fan_on | integer | 1 |
| temp_degc | double precision | -999.0 |
| exptime_sec | double precision | 0.0 |
| psf_pixels | double precision | 2.037 |
| last_updated | text | 2019-03-31T18:53:11.680127 |
| time_recorded | timestamp with time zone | 2019-03-31 18:53:11.696556+00:00 |
| dos_instance | text | extern |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2019-03-31 18:53:11.699890+00:00 |
| row_status_user | text | desi_writer |

### ocs_positioning

Shared variable `OCS_POSITIONING`.

| Field | Type | Example |
|---|---|---|
| ocs_positioning | integer | 1 |
| expid | integer | 56197 |
| targets | integer | 5000 |
| iteration | integer | 0 |
| rms | double precision | 0.0632 |
| enabled | integer | 4208 |
| disabled | integer | 773 |
| ontarget | integer | 85 |
| fraction | double precision | 0.0202 |
| converged | integer | 0 |
| last_expid | integer |  |
| last_targets | integer |  |
| last_iteration | integer |  |
| last_rms | double precision |  |
| last_enabled | integer |  |
| last_disabled | integer |  |
| last_ontarget | integer |  |
| last_fraction | double precision |  |
| last_converged | integer |  |
| time_recorded | timestamp with time zone | 2020-06-04 04:56:53.140581+00:00 |
| dos_instance | text | desisim_20200526 |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2020-06-04 04:56:53.141723+00:00 |
| row_status_user | text | desi_writer |
| onfraction | double precision |  |
| cvgfraction | double precision |  |
| loop_converged | integer |  |
| last_onfraction | double precision |  |
| last_cvgfraction | double precision |  |
| last_loop_converged | integer |  |
| last_last_expid | integer |  |
| trms | double precision |  |
| posrms | double precision |  |
| turbrms | double precision |  |
| notontarget | integer |  |
| last_posrms | double precision |  |
| last_turbrms | double precision |  |
| last_notontarget | integer |  |
| turbclip | integer |  |

### environmentmonitor_dome

Shared variable `ENVIRONMENTMONITOR_DOME`.

| Field | Type | Example |
|---|---|---|
| environmentmonitor_dome | integer | 1 |
| dome_timestamp | text | 2019-03-27 03:10:14 |
| platform | double precision | -99.9 |
| stairs_upper | double precision | -99.9 |
| stairs_mid | double precision | -99.9 |
| stairs_lower | double precision | -99.9 |
| dome_left_upper | double precision | -99.9 |
| dome_left_lower | double precision | -99.9 |
| dome_back_upper | double precision | -99.9 |
| dome_back_lower | double precision | -99.9 |
| dome_right_upper | double precision | -99.9 |
| dome_right_lower | double precision | -99.9 |
| lcr_ceiling | double precision | 14.9 |
| lcr_n_wall_inside | double precision | 14.9 |
| lcr_w_wall_inside | double precision | 14.6 |
| lcr_floor | double precision | 13.6 |
| shack_ceiling | double precision | 15.9 |
| shack_wall | double precision | 14.3 |
| lcr_ambient_n | double precision | 14.5 |
| lcr_ambient_s | double precision | 15.4 |
| lcr_n_wall_outside | double precision | 12.3 |
| lcr_w_wall_outside | double precision | 12.9 |
| c_floor | double precision | 12.5 |
| telescope_base | double precision | 12.1 |
| utility_room | double precision | 15.4 |
| utility_n_wall | double precision | 14.9 |
| scr_e_wall_coude | double precision | 12.5 |
| scr_e_wall_computer | double precision | 13.4 |
| scr_roof | double precision | 13.7 |
| scr_roof_ambient | double precision | 13.3 |
| glycol | double precision | -3.4 |
| main_floor | double precision |  |
| time_recorded | timestamp with time zone | 2019-03-27 03:10:16.733842+00:00 |
| dos_instance | text | extern |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2019-03-27 03:10:16.741833+00:00 |
| row_status_user | text | desi_writer |
| shutter_upper | integer |  |
| shutter_lower | integer |  |
| lights_high | integer |  |
| lights_low | integer |  |
| mirror_cover | integer |  |
| mirror_cooling | integer |  |
| catwalk_temperature | double precision |  |
| catwalk_split | double precision |  |
| catwalk_humidity | double precision |  |
| catwalk_dewpoint | double precision |  |
| mirror_ventfans | integer |  |
| dome_floor_s | double precision |  |
| dome_floor_ne | double precision |  |
| dome_floor_nw | double precision |  |
| between_twilight | integer |  |
| calibration_comment | text |  |
| calibration_trigger | integer |  |
| louvers_left | ARRAY |  |
| louvers_right | ARRAY |  |
| calibration_state | text |  |
| b29fan | integer |  |
| dome_circulation_fan | double precision |  |

### environmentmonitor_ups

Shared variable `ENVIRONMENTMONITOR_UPS`.

| Field | Type | Example |
|---|---|---|
| environmentmonitor_ups | integer | 1 |
| ups_timestamp | text | 2019-03-27 03:10:14 |
| status | text | System Normal - On Line(7) |
| state_output | text | On(1) |
| state_charger | text | Battery String is Resting(4) |
| state_battery_health | integer | 86 |
| battery_test_started | text | false(0) |
| batter_test_result | text | Passed(2) |
| alarm_major | integer | 0 |
| alarm_on | integer | 0 |
| alarm_shutdown_imminent | integer | 0 |
| alarm_check_battery | integer | 0 |
| battery_seconds_left | double precision | 10458.0 |
| battery_percent_left | double precision | 100.0 |
| ambient_temp | double precision | 17.4 |
| batterytemp | double precision | 16.7 |
| input_volts_phase_a | double precision | 278.1 |
| input_volts_phase_b | double precision | 273.4 |
| input_volts_phase_c | double precision | 274.4 |
| input_total_amps | double precision | 44.3 |
| output_watts_phase_a | double precision | 2200.0 |
| output_watts_phase_b | double precision | 4200.0 |
| output_watts_phase_c | double precision | 3100.0 |
| output_volt_amps_phase_a | double precision | 2400.0 |
| output_volt_amps_phase_b | double precision | 4400.0 |
| output_volt_amps_phase_c | double precision | 3500.0 |
| time_recorded | timestamp with time zone | 2019-03-27 03:10:14.728242+00:00 |
| dos_instance | text | extern |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2019-03-27 03:10:14.735143+00:00 |
| row_status_user | text | desi_writer |
| between_twilight | integer |  |
| input_phase_a | double precision |  |
| input_phase_b | double precision |  |
| input_phase_c | double precision |  |
| npos | integer |  |

### environmentmonitor_computer

Shared variable `ENVIRONMENTMONITOR_COMPUTER`.

| Field | Type | Example |
|---|---|---|
| environmentmonitor_computer | integer | 1 |
| compterroom_timestamp | text | 2019-03-27 03:10:14 |
| humidity | double precision | 26.5 |
| dewpoint | double precision | -1.4 |
| ambient_temp | double precision | 17.9 |
| hygrometer_temp | double precision | 18.2 |
| time_recorded | timestamp with time zone | 2019-03-27 03:10:15.730868+00:00 |
| dos_instance | text | extern |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2019-03-27 03:10:15.736809+00:00 |
| row_status_user | text | desi_writer |
| glycol_in | double precision |  |
| glycol_return | double precision |  |
| between_twilight | integer |  |

### tcs_info

Shared variable `TCS_INFO`.

| Field | Type | Example |
|---|---|---|
| tcs_info | integer | 1 |
| tcs_timestamp | text |  |
| date_ut | text | 2019-01-31 17:02:26.967 |
| st | text |  |
| mjd | double precision | 58514.710463 |
| zd | double precision | 73.349899 |
| airmass | double precision | 3.455252 |
| parallactic | double precision | 62.31074 |
| moon_ra | double precision | 265.540181 |
| moon_dec | double precision | -20.668064 |
| tracking | integer | 0 |
| slew_timer | double precision | 0.0 |
| beyond_pole | integer | 0 |
| mount_incontrol | integer | 0 |
| mount_inposition | integer | 0 |
| mount_ha | double precision | 89.502176 |
| mount_ha_sexagesimal | text | +05:58:00.522 |
| mount_dec | double precision | 31.967558 |
| mount_dec_sexagesimal | text | +031:58:03.209 |
| mount_az | double precision | 297.694236 |
| mount_az_sexagesimal | text | 297:41:39.251 |
| mount_el | double precision | 16.650101 |
| mount_el_sexagesimal | text | 16:39:00.362 |
| mount_offset_ra | double precision | 0.0 |
| mount_offset_dec | double precision | 0.0 |
| sky_ra | double precision | 184.894802 |
| sky_ra_sexagesimal | text | 12:19:34.753 |
| sky_dec | double precision | 32.070716 |
| sky_dec_sexagesimal | text | +32:04:14.579 |
| target_ra | double precision | 262.75577 |
| target_ra_sexagesimal | text | 17:31:01.385 |
| target_dec | double precision | 31.9633 |
| target_dec_sexagesimal | text | +31:57:47.880 |
| target_az | double precision | 273.018266 |
| target_az_sexagesimal | text | 273:01:05.759 |
| target_el | double precision | 80.070596 |
| target_el_sexagesimal | text | 80:04:14.147 |
| target_offset_ra | double precision | 0.0 |
| target_offset_dec | double precision | 0.0 |
| epoch | double precision | 2000.0 |
| equinox | double precision | 2000.0 |
| guider_offset_ra | double precision | 0.0 |
| guider_offset_dec | double precision | 0.0 |
| at_zenith | integer | 0 |
| at_whitespot | integer | 0 |
| at_se_annex | integer | 0 |
| dome_az | double precision | 297.694236 |
| dome_inposition | integer | 0 |
| mirror_ready | integer | 0 |
| time_recorded | timestamp with time zone | 2019-01-31 17:02:27.417953+00:00 |
| connected | integer | 1 |
| tcs_state | text | READY |
| dos_instance | text | klaus |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2019-01-31 17:02:27.426671+00:00 |
| row_status_user | text | desi_writer |
| glycol | double precision |  |
| simulated | integer |  |
| moon_sep | double precision |  |

### ocs_obsinfo

Shared variable `OCS_OBSINFO`.

| Field | Type | Example |
|---|---|---|
| ocs_obsinfo | integer | 1 |
| observers | text | DESIObserver |
| lead | text | RunManager |
| program | text | Commissioning |
| propid | text | 2019B-5000 |
| time_recorded | timestamp with time zone | 2020-07-29 20:14:24.906300+00:00 |
| dos_instance | text | desisim_20200729 |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2020-07-29 20:14:24.906966+00:00 |
| row_status_user | text | desi_writer |

### skycam_telemetry

Shared variable `SKYCAM_TELEMETRY`.

| Field | Type | Example |
|---|---|---|
| skycam_telemetry | integer | 1 |
| last_updated | text | 2020-09-10T20:58:58.233933 |
| unit | integer | 1 |
| role | text | SKYCAM1 |
| ccdtemp | double precision | 14.94 |
| fanenabled | integer | 2 |
| fanpower | integer | 50 |
| settemp | double precision | 15.0 |
| ccdpower | double precision | 0.0 |
| cooling | integer | 1 |
| status | text | SUCCESS |
| time_recorded | timestamp with time zone | 2020-09-10 20:58:58.234542+00:00 |
| dos_instance | text | skytest |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2020-09-10 20:58:58.235215+00:00 |
| row_status_user | text | desi_writer |
| simulated | integer |  |

### ocs_gfadata

Shared variable `OCS_GFADATA`.

| Field | Type | Example |
|---|---|---|
| ocs_gfadata | integer | 1 |
| dtheta | double precision |  |
| eta0 | double precision |  |
| f1 | double precision |  |
| f2 | double precision |  |
| f3 | double precision |  |
| f4 | double precision |  |
| fieldrot | double precision |  |
| fwhmsec | double precision |  |
| hexrate | double precision |  |
| hexrot | double precision |  |
| hextot | double precision |  |
| magoff | double precision | 0.6 |
| ngfa | integer |  |
| ngood | integer |  |
| pixscale | double precision |  |
| project | text |  |
| psi | double precision |  |
| refract | double precision |  |
| rmsx | double precision |  |
| rmsy | double precision |  |
| rnutat | double precision |  |
| rpolar | double precision |  |
| rprecess | double precision |  |
| rtheta | double precision |  |
| rtheta0 | double precision |  |
| rthetaa | double precision |  |
| rthetaaberr | double precision |  |
| rthetatot | double precision |  |
| rzrot | double precision |  |
| s | double precision |  |
| seqid | integer |  |
| tempscale | double precision |  |
| theta1 | double precision |  |
| thetacorr | double precision |  |
| xi0 | double precision |  |
| zd | double precision |  |
| time_recorded | timestamp with time zone | 2020-12-18 03:57:13.859744+00:00 |
| dos_instance | text | extern |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2020-12-18 03:57:13.861459+00:00 |
| row_status_user | text | desi_writer |

### sky_skylevel

Shared variable `SKY_SKYLEVEL`.

| Field | Type | Example |
|---|---|---|
| sky_skylevel | integer | 366587 |
| time_recorded | timestamp with time zone | 2025-10-20 07:40:33.001003+00:00 |
| dos_instance | text | desi_20251019 |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2025-10-20 07:40:33.002374+00:00 |
| row_status_user | text | desi_writer |
| average | double precision | 1.464 |
| skycam1 | double precision | 1.39 |
| skycam0 | double precision | 1.527 |

### lut_configuration

Shared variable `LUT_CONFIGURATION`.

| Field | Type | Example |
|---|---|---|
| lut_configuration | integer | 1 |
| usetellut | integer | 1 |
| usetemplut | integer | 1 |
| useztrim | integer | 0 |
| temp0 | double precision | 7.0 |
| tellutmode | ARRAY | [1, 1, 1, 1, 1, 1] |
| useaos | integer | 0 |
| time_recorded | timestamp with time zone | 2021-02-19 15:36:54.122372+00:00 |
| dos_instance | text | desi_20210218 |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2021-02-19 15:36:54.123605+00:00 |
| row_status_user | text | desi_writer |

### lut_lookup

Shared variable `LUT_LOOKUP`.

| Field | Type | Example |
|---|---|---|
| lut_lookup | integer | 1 |
| az | double precision | 65.122662 |
| el | double precision | 89.826659 |
| temperature | double precision | 10.47 |
| use_ztrim | integer | 0 |
| use_temp | integer | 1 |
| use_table | integer | 1 |
| use_aos | integer | 0 |
| hexapod | ARRAY | [1140.0, -480.0, 371.835, -3.0, 25.0, 0.0, 0.0] |
| time_recorded | timestamp with time zone | 2021-02-19 19:13:35.408225+00:00 |
| dos_instance | text | desi_20210218 |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2021-02-19 19:13:35.409404+00:00 |
| row_status_user | text | desi_writer |
| tel_lookup | ARRAY |  |
| temp_lookup | ARRAY |  |

### etc_seeing

Shared variable `ETC_SEEING`.

| Field | Type | Example |
|---|---|---|
| etc_seeing | integer | 1 |
| seeing | double precision | nan |
| last_updated | text | 2021-03-10T11:51:50.894211 |
| time_recorded | timestamp with time zone | 2021-03-10 11:51:50.899488+00:00 |
| dos_instance | text | desi_20210309 |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2021-03-10 11:51:50.900023+00:00 |
| row_status_user | text | desi_writer |

### etc_skylevel

Shared variable `ETC_SKYLEVEL`.

| Field | Type | Example |
|---|---|---|
| etc_skylevel | integer | 1 |
| skylevel | double precision | nan |
| last_updated | text | 2021-03-10T11:51:50.894211 |
| time_recorded | timestamp with time zone | 2021-03-10 11:51:50.909456+00:00 |
| dos_instance | text | desi_20210309 |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2021-03-10 11:51:50.909887+00:00 |
| row_status_user | text | desi_writer |

### etc_requests

Shared variable `ETC_REQUESTS`.

| Field | Type | Example |
|---|---|---|
| etc_requests | integer | 1 |
| about_to_split | integer | 0 |
| split_request | integer | 0 |
| about_to_stop | integer | 0 |
| stop_request | integer | 0 |
| time_recorded | timestamp with time zone | 2021-03-09 22:55:33.412086+00:00 |
| dos_instance | text | desi_20210309 |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2021-03-09 22:55:33.413815+00:00 |
| row_status_user | text | desi_writer |

### etc_transparency

Shared variable `ETC_TRANSPARENCY`.

| Field | Type | Example |
|---|---|---|
| etc_transparency | integer | 1 |
| transparency | double precision | 0.0 |
| last_updated | text | 2021-03-09T22:57:56.750673 |
| time_recorded | timestamp with time zone | 2021-03-09 22:57:56.760682+00:00 |
| dos_instance | text | desi_20210309 |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2021-03-09 22:57:56.762318+00:00 |
| row_status_user | text | desi_writer |

### performance_night

Shared variable `PERFORMANCE_NIGHT`.

| Field | Type | Example |
|---|---|---|
| performance_night | integer | 1 |
| obsday | text | 20210409 |
| scheduled_shutdown | integer | 0 |
| dawn | text | 05:08:56 |
| dusk | text | 19:45:15 |
| interval | double precision | 5.0 |
| seconds_between_nautical_twilight | integer | 33821 |
| time_recorded | timestamp with time zone | 2021-04-09 22:53:58.375797+00:00 |
| dos_instance | text | desi_20210408 |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2021-04-09 22:53:58.376548+00:00 |
| row_status_user | text | desi_writer |
| seconds_between_twilight | integer |  |

### performance_current

Shared variable `PERFORMANCE_CURRENT`.

| Field | Type | Example |
|---|---|---|
| performance_current | integer | 1 |
| system_ready | integer | 1 |
| nfs | integer | 0 |
| ocs_active | integer | 0 |
| guider_loop | integer | 0 |
| focus_loop | integer | 0 |
| sky_loop | integer | 0 |
| illuminator | integer | 0 |
| specman_shutter | integer | 0 |
| specman_digitize | integer | 0 |
| tcs_tracking | integer | 0 |
| tcs_incontrol | integer | 0 |
| tcs_slewing | integer | 0 |
| gfa_vccd | integer | 1 |
| spectrograph_vccd | integer | 1 |
| gfa_opsstate | integer | 1 |
| petal_opsstate | integer | 0 |
| opsstate | integer | 0 |
| weather | integer | 0 |
| instrument | integer | 0 |
| mayall | integer | 1 |
| other | integer | 0 |
| obsday | text | 20210409 |
| time_recorded | timestamp with time zone | 2021-04-09 22:53:58.412229+00:00 |
| dos_instance | text | desi_20210408 |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2021-04-09 22:53:58.413387+00:00 |
| row_status_user | text | desi_writer |
| desi_interlock | integer |  |
| ocs_monitor | integer |  |
| mirror_cover | integer |  |
| dome_shutter | integer |  |
| seq_active | integer |  |
| fiducials | integer |  |
| move_prepare | integer |  |
| move_execute | integer |  |
| nfsproc | integer |  |
| gfaproc | integer |  |
| posproc | integer |  |
| fvcproc | integer |  |
| forproc | integer |  |
| spotmatch | integer |  |
| last_updated | text |  |
| acquisition | integer |  |
| idle | integer |  |
| specman_prepare | integer |  |
| ready | integer |  |
| fvc | integer |  |
| about_to_split | integer |  |
| split_request | integer |  |
| about_to_stop | integer |  |
| stop_request | integer |  |
| monitored | integer |  |
| handle_fvc | integer |  |
| gfaadjust | integer |  |
| nfsadjust | integer |  |
| surveyobs | integer |  |
| obs | integer |  |
| nfsrequest | integer |  |

### pc_ptl_status

Shared variable `PC_PTL-STATUS`.

| Field | Type | Example |
|---|---|---|
| pc_ptl_status | integer | 1 |
| pospwr_ps2_en | integer | 0 |
| canbrd1_en | integer | 1 |
| gfapwr_en | integer | 0 |
| gfa_fan_out_en | integer |  |
| gfa_fan_in_en | integer |  |
| canbusfault | integer | 0 |
| pcid | integer | 1 |
| time | timestamp with time zone | 2020-11-03 22:06:37.400641+00:00 |
| canbrd2_en | integer | 1 |
| buff_en2 | integer | 1 |
| pospwr_ps2_fbk | integer | 0 |
| pospwr_ps1_fbk | integer | 0 |
| ccdbias | integer | 0 |
| status | jsonb | {} |
| fxc_okay | integer | 0 |
| ccdbiasenabled | integer | 0 |
| telemetryfault | integer | 0 |
| pospwr_ps1_en | integer | 0 |
| buff_en1 | integer | 1 |
| gfa_ovrtmp | integer | 0 |
| tec_ctrl | integer | 0 |
| time_recorded | timestamp with time zone | 2020-11-03 22:06:37.530836+00:00 |
| dos_instance | text | extern |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2020-11-03 22:06:37.536176+00:00 |
| row_status_user | text | desi_writer |
| simulated | integer |  |

### pc_ptl_sensors

Shared variable `PC_PTL-SENSORS`.

| Field | Type | Example |
|---|---|---|
| pc_ptl_sensors | integer | 269528 |
| gxbtime | timestamp with time zone | 2020-12-04 22:08:55.539479+00:00 |
| gfa_fan_in_pwm | double precision | 15.0 |
| adc_gfa | double precision | 11.27 |
| adctime | timestamp with time zone | 2020-12-04 22:08:49.980366+00:00 |
| gfa_fan_out_tach | integer | 7150 |
| adc_fan | double precision | 12.25 |
| pcid | integer | 8 |
| gfa_fan_out_pwm | double precision | 15.0 |
| gxbcur | double precision | 1.610379 |
| gfatime | timestamp with time zone | 2020-12-04 22:08:58.597500+00:00 |
| temptime | timestamp with time zone | 2020-12-04 22:08:55.544474+00:00 |
| gfa_fan_in_tach | integer | 10201 |
| adc_buf | double precision | 3.28 |
| adc_bb | double precision | 5.23 |
| fpp_temp_sensor_3 | double precision | 10.937 |
| pbox_temp_sensor | double precision | 20.5 |
| adc_can | double precision | 12.23 |
| fpp_temp_sensor_2 | double precision | 11.312 |
| fpp_temp_sensor_1 | double precision | 15.625 |
| time | timestamp with time zone | 2020-12-04 22:08:58.914472+00:00 |
| gxb_temp_sensor | double precision | 19.40625 |
| time_recorded | timestamp with time zone | 2020-12-04 22:08:58.921855+00:00 |
| dos_instance | text | extern |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2020-12-04 22:08:58.948420+00:00 |
| row_status_user | text | desi_writer |
| simulated | integer | 0 |
| fpp_temp_sensor_4 | double precision |  |
| fpp_temp_sensor_5 | double precision |  |
| fpp_temp_sensor_6 | double precision |  |
| fpp_temp_sensor_7 | double precision |  |
| fpp_temp_sensor_8 | double precision |  |
| fpp_temp_sensor_9 | double precision |  |
| fpp_temp_sensor_10 | double precision |  |
| fpp_temp_sensor_11 | double precision |  |
| fpp_temp_sensor_12 | double precision |  |
| fpp_temp_sensor_13 | double precision |  |
| adc_split_v | double precision |  |
| adc_ppwr2_v | double precision |  |
| adc_ppwr1_c | double precision |  |
| adc_ppwr2_c | double precision |  |
| adc_ppwr1_v | double precision |  |

### pc_ptl_powerup

Shared variable `PC_PTL-POWERUP`.

| Field | Type | Example |
|---|---|---|
| pc_ptl_powerup | integer | 1 |
| time | timestamp with time zone | 2020-11-06 03:37:55.832326+00:00 |
| pcid | integer | 907 |
| psfid_sysclks | jsonb |  |
| thresholds | jsonb | {'CURR_GXB_WARN': 100, 'TACH_FAN_WARN': 2000, 'TE... |
| status | jsonb | {} |
| network_status | jsonb | FAILED |
| time_recorded | timestamp with time zone | 2020-11-06 03:37:55.843384+00:00 |
| dos_instance | text | extern |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2020-11-06 03:37:55.844104+00:00 |
| row_status_user | text | desi_writer |
| simulated | integer |  |
| posfid_sysclks | jsonb |  |

### pc_ptl_temps

Shared variable `PC_PTL-TEMPS`.

| Field | Type | Example |
|---|---|---|
| pc_ptl_temps | integer | 1 |
| time | timestamp with time zone | 2020-11-06 03:37:55.831579+00:00 |
| pcid | integer | 907 |
| posfid_imons | jsonb | {'9070': {'907000': None, '907001': None, '907002... |
| posfid_temps | jsonb | {'999': 32.92} |
| posfid_temps_max | double precision | 32.92 |
| posfid_temps_mean | double precision | 32.920000000000016 |
| posfid_temps_median | double precision | 32.92 |
| posfid_state | text | unknown |
| posfid_instatesince | double precision |  |
| posfid_timelastalarm | double precision |  |
| pos_temps_mean | double precision |  |
| pos_temps_median | double precision |  |
| pos_temps_max | double precision |  |
| posfid_temps_n_above_th | integer | 0 |
| fid_temps | jsonb |  |
| fid_temps_max | double precision |  |
| fid_temps_mean | double precision |  |
| fid_temps_median | double precision |  |
| fid_temps_n_above_th | integer |  |
| onewire | jsonb |  |
| threshold_fid_warn | double precision |  |
| threshold_fid_alarm | double precision |  |
| threshold_pos_warn | double precision |  |
| threshold_pos_alarm | double precision |  |
| time_recorded | timestamp with time zone | 2020-11-06 03:37:55.849310+00:00 |
| dos_instance | text | extern |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2020-11-06 03:37:55.850637+00:00 |
| row_status_user | text | desi_writer |
| simulated | integer |  |

### hexapod_rotator

Shared variable `HEXAPOD_ROTATOR`.

| Field | Type | Example |
|---|---|---|
| hexapod_rotator | integer | 1 |
| rot_enabled | integer | 0 |
| rot_stopped | integer | 1 |
| simulated | integer | 0 |
| rot_offset | double precision | 0.0 |
| rot_rate | double precision | 0.0 |
| rot_interval | double precision | 60.0 |
| ra | double precision |  |
| dec | double precision |  |
| enabled | integer | 0 |
| time_recorded | timestamp with time zone | 2020-11-12 15:01:18.980958+00:00 |
| dos_instance | text | desisim_20201111 |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2020-11-12 15:01:18.982177+00:00 |
| row_status_user | text | desi_writer |
| expid | integer |  |

### environmentmonitor_fpe

Shared variable `ENVIRONMENTMONITOR_FPE`.

| Field | Type | Example |
|---|---|---|
| environmentmonitor_fpe | integer | 1 |
| fpe_timestamp | text | 2020-11-13 14:52:37 |
| humidity | double precision | 0.97 |
| temperature | double precision | 9.99 |
| dewpoint | double precision | -40.0 |
| shack_dryair_temperature | double precision | 19.6 |
| shack_dryair_water_ppm | double precision | 5806.0 |
| shack_dryair_pressure_abs_bar | double precision | 0.8 |
| shack_dryair_pressure_gauge_psi | double precision | 0.0 |
| shack_dryair_dewpoint_dryer | double precision | -3.3 |
| shack_dryair_dewpoint_atmos | double precision | -0.5 |
| fpe_dryair_temperature | double precision | 31.0 |
| fpe_dryair_water_ppm | double precision | 1.0 |
| fpe_dryair_pressure_abs_bar | double precision | 5.665 |
| fpe_dryair_pressure_gauge_psi | double precision | 70.8 |
| fpe_dryair_dewpoint_dryer | double precision | -66.1 |
| fpe_dryair_dewpoint_atmos | double precision | -77.5 |
| time_recorded | timestamp with time zone | 2020-11-13 14:52:38.594504+00:00 |
| dos_instance | text | extern |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2020-11-13 14:52:38.601261+00:00 |
| row_status_user | text | desi_writer |
| coude_humidity | double precision |  |
| coude_temperature | double precision |  |
| coude_dewpoint | double precision |  |
| fp_glycol_supply | double precision |  |
| fp_glycol_return_a | double precision |  |
| fp_glycol_return_b | double precision |  |
| cryostat_glycol_supply | double precision |  |
| cryostat_glycol_return | double precision |  |
| between_twilight | integer |  |

### fxc_adcs

Shared variable `FXC_ADCS`.

| Field | Type | Example |
|---|---|---|
| fxc_adcs | integer | 1 |
| adc3 | integer | 0 |
| adc2 | integer | 0 |
| adc6 | integer | 2048 |
| adc0 | integer | 0 |
| adc5 | integer | 2033 |
| adc1 | integer | 0 |
| adc4 | integer | 976 |
| time_recorded | timestamp with time zone | 2020-11-17 17:15:57.128832+00:00 |
| dos_instance | text | extern |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2020-11-17 17:15:57.141174+00:00 |
| row_status_user | text | desi_writer |

### fxc_chiller

Shared variable `FXC_CHILLER`.

| Field | Type | Example |
|---|---|---|
| fxc_chiller | integer | 39909 |
| chiller_refrigerator_running_time | text | 2020-11-18T20:53:33.932392+00:00 |
| chiller_setpoint | double precision | 10.0 |
| chiller_status_time | text | 2020-11-18T20:53:33.923409+00:00 |
| chiller_fluid_level | integer | 1 |
| chiller_running_time | text | 2020-11-18T20:53:33.932206+00:00 |
| chiller_running | integer | 1 |
| chiller_fluid_level_time | text | 2020-11-18T20:53:33.932001+00:00 |
| chiller_status | jsonb | {'DI1': 14, 'DI2': 7, 'DO1': 40, 'DO2': 174, 'PID... |
| chiller_setpoint_time | text | 2020-11-18T20:53:33.931695+00:00 |
| chiller_refrigerator_running | integer | 0 |
| time_recorded | timestamp with time zone | 2020-11-18 20:53:34.842655+00:00 |
| dos_instance | text | extern |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2020-11-18 20:53:35.012852+00:00 |
| row_status_user | text | desi_writer |
| chiller_pressure | double precision |  |
| chiller_flowrate | double precision |  |
| chiller_temperature | double precision |  |
| chiller_heat_pct | double precision |  |
| chiller_cool_pct | double precision |  |
| chiller_error1bits | integer |  |
| chiller_error2bits | integer |  |
| chiller_warnbits | integer |  |

### fxc_temps

Shared variable `FXC_TEMPS`.

| Field | Type | Example |
|---|---|---|
| fxc_temps | integer | 1 |
| hxa_air | double precision | 16.937 |
| fpr_2 | double precision | 16.937 |
| fpr_1 | double precision | 16.875 |
| exterior_air | double precision | 18.125 |
| fpe_air_high | double precision | 17.812 |
| fpe_air_low | double precision | 16.937 |
| coolant_in | double precision | 17.0 |
| adjacent_ptl | double precision | 16.875 |
| coolant_out | double precision | 17.062 |
| air_fxc | double precision | 20.875 |
| time_recorded | timestamp with time zone | 2020-11-17 17:15:56.907882+00:00 |
| dos_instance | text | extern |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2020-11-17 17:15:56.992291+00:00 |
| row_status_user | text | desi_writer |

### fxc_pid

Shared variable `FXC_PID`.

| Field | Type | Example |
|---|---|---|
| fxc_pid | integer | 435 |
| pid_target | double precision | 0.0 |
| pid_dgain | double precision | 0.0 |
| pid_dmin | double precision | 0.0 |
| pid_imin | double precision | 0.0 |
| pid_sensor | double precision |  |
| pid_igain | double precision | 0.0 |
| pid_enabled | integer | 0 |
| pid_smax | double precision | 0.0 |
| pid_smin | double precision | 0.0 |
| pid_offset | double precision | 0.0 |
| pid_pgain | double precision | 0.0 |
| time_recorded | timestamp with time zone | 2020-11-18 20:53:19.689003+00:00 |
| dos_instance | text | extern |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2020-11-18 20:53:19.737986+00:00 |
| row_status_user | text | desi_writer |

### performance_accumulated

Shared variable `PERFORMANCE_ACCUMULATED`.

| Field | Type | Example |
|---|---|---|
| performance_accumulated | integer | 1 |
| system_ready | double precision | 5.04 |
| nfs | double precision | 0.0 |
| ocs_active | double precision | 0.0 |
| guider_loop | double precision | 0.0 |
| focus_loop | double precision | 0.0 |
| sky_loop | double precision | 0.0 |
| illuminator | double precision | 0.0 |
| specman_shutter | double precision | 0.0 |
| specman_digitize | double precision | 0.0 |
| tcs_tracking | double precision | 0.0 |
| tcs_incontrol | double precision | 0.0 |
| tcs_slewing | double precision | 0.0 |
| gfa_vccd | double precision | 5.02 |
| spectrograph_vccd | double precision | 5.02 |
| gfa_opsstate | double precision | 5.03 |
| petal_opsstate | double precision | 0.0 |
| opsstate | double precision | 0.0 |
| weather | double precision | 0.0 |
| instrument | double precision | 0.0 |
| mayall | double precision | 5.05 |
| other | double precision | 0.0 |
| obsday | text | 20210409 |
| time_recorded | timestamp with time zone | 2021-04-09 22:53:58.418345+00:00 |
| dos_instance | text | desi_20210408 |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2021-04-09 22:53:58.419361+00:00 |
| row_status_user | text | desi_writer |
| desi_interlock | double precision |  |
| ocs_monitor | double precision |  |
| mirror_cover | double precision |  |
| dome_shutter | double precision |  |
| seq_active | double precision |  |
| fiducials | double precision |  |
| move_prepare | double precision |  |
| move_execute | double precision |  |
| nfsproc | double precision |  |
| gfaproc | double precision |  |
| posproc | double precision |  |
| fvcproc | double precision |  |
| forproc | double precision |  |
| spotmatch | double precision |  |
| last_updated | text |  |
| acquisition | double precision |  |
| idle | double precision |  |
| specman_prepare | double precision |  |
| ready | double precision |  |
| fvc | double precision |  |
| about_to_split | double precision |  |
| split_request | double precision |  |
| about_to_stop | double precision |  |
| stop_request | double precision |  |
| monitored | double precision |  |
| time_between_twilight | integer |  |
| handle_fvc | double precision |  |
| gfaadjust | double precision |  |
| nfsadjust | double precision |  |
| surveyobs | double precision |  |
| obs | double precision |  |
| nfsrequest | integer |  |

### fxc_misc

Shared variable `FXC_MISC`.

| Field | Type | Example |
|---|---|---|
| fxc_misc | integer | 46341 |
| bb_spare_en_time | text | 2020-11-18T23:18:10.000588+00:00 |
| bb_chill_en_time | text | 2020-11-18T23:18:09.159764+00:00 |
| bb_posfid_en_time | text | 2020-11-18T23:18:09.844336+00:00 |
| bb_posfid_en | text | off |
| fan_48v_ok_time | text | 2020-11-18T23:17:44.307665+00:00 |
| last_sw_limits_error_time | text | 2020-11-18T21:12:09.778861+00:00 |
| bb_chill_en | text | on |
| sw_limits_time | text | 2020-11-18T20:53:19.617682+00:00 |
| sw_limits_en_time | text | 2020-11-18T20:53:33.854984+00:00 |
| auto_refer_on_period_time | text | 2020-11-18T20:53:19.615931+00:00 |
| fan_48v_ok | text | off |
| auto_refer_on_en_time | text | 2020-11-18T20:53:19.615730+00:00 |
| bb_fp1_en_time | text | 2020-11-18T23:18:09.297388+00:00 |
| fan_48v_en | text | off |
| sw_limits | jsonb | {'ADCS:ADC4': [-1, 5000, 'Dry Air Flow'], 'ADCS:A... |
| last_sw_limits_error | text |  |
| auto_refer_on_en | integer | 0 |
| auto_refer_on_period | integer | 300 |
| smoke_tripped_time | text | 2020-11-19T04:10:52.505866+00:00 |
| bb_fp1_en | text | off |
| smoke_tripped | text | off |
| bb_fp2_en | text | off |
| sw_limits_en | integer | 0 |
| bb_fp2_en_time | text | 2020-11-18T23:18:09.560441+00:00 |
| bb_spare_en | text | off |
| fan_48v_en_time | text | 2020-11-18T23:17:44.592386+00:00 |
| time_recorded | timestamp with time zone | 2020-11-19 04:10:52.512124+00:00 |
| dos_instance | text | extern |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2020-11-19 04:10:52.529265+00:00 |
| row_status_user | text | desi_writer |

### fxc_vaisala

Shared variable `FXC_VAISALA`.

| Field | Type | Example |
|---|---|---|
| fxc_vaisala | integer | 1 |
| v_fpd_dewpoint | double precision | -29.02 |
| v_se_ext_id | integer | 43 |
| v_fpd_temperature | double precision | 18.35 |
| v_fpd_time | text | 2020-11-18T16:10:02.289466+00:00 |
| v_c3c4_humidity | double precision | 0.06 |
| v_c3c4_id | integer | 42 |
| v_c3c4_dewpoint | double precision | -59.03 |
| v_se_ext_dewpoint | double precision | -3.37 |
| v_fpd_id | integer | 44 |
| v_c3c4_temperature | double precision | 17.82 |
| v_se_ext_humidity | double precision | 22.94 |
| v_fpd_humidity | double precision | 1.99 |
| v_se_ext_temperature | double precision | 17.59 |
| v_se_ext_time | text | 2020-11-18T16:10:02.289466+00:00 |
| v_c3c4_time | text | 2020-11-18T16:10:02.289466+00:00 |
| time_recorded | timestamp with time zone | 2020-11-18 16:10:03.184364+00:00 |
| dos_instance | text | extern |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2020-11-18 16:10:03.206329+00:00 |
| row_status_user | text | desi_writer |

### fxc_thr

Shared variable `FXC_THR`.

| Field | Type | Example |
|---|---|---|
| fxc_thr | integer | 1 |
| t_relay_set | integer | 0 |
| t_humidity_lim_lo | integer | 0 |
| t_alarm | integer | 20 |
| t_id | text | 7e_00100000254a |
| t_timerb | integer | 61122 |
| t_timera | integer | 23179 |
| t_humidity | double precision | 1.625 |
| t_temp_lim_lo | integer | 0 |
| t_dewpoint_lim_hi | integer | 15 |
| t_temp_lim_hi | integer | 35 |
| t_relay_func | integer | 0 |
| t_temperature | double precision | 19.75 |
| t_time | text | 2020-11-18T20:08:36.264642+00:00 |
| t_dewpoint | double precision | -32.75 |
| t_relay_state | integer | 0 |
| t_dewpoint_lim_lo | integer | -128 |
| t_humidity_lim_hi | integer | 85 |
| time_recorded | timestamp with time zone | 2020-11-18 20:08:37.148211+00:00 |
| dos_instance | text | extern |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2020-11-18 20:08:37.171890+00:00 |
| row_status_user | text | desi_writer |

### fxc_interlocks

Shared variable `FXC_INTERLOCKS`.

| Field | Type | Example |
|---|---|---|
| fxc_interlocks | integer | 2084 |
| interlock_fans | integer | 0 |
| interlock_owthr | integer | 0 |
| interlock_sw_limits | integer | 0 |
| interlock_ok | integer | 1 |
| interlock_smoke | integer | 0 |
| time_recorded | timestamp with time zone | 2020-11-18 20:57:17.311586+00:00 |
| dos_instance | text | extern |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2020-11-18 20:57:17.320540+00:00 |
| row_status_user | text | desi_writer |
| last_interlock | text |  |
| last_interlock_time | timestamp with time zone |  |

### fxc_fans

Shared variable `FXC_FANS`.

| Field | Type | Example |
|---|---|---|
| fxc_fans | integer | 1 |
| fan1_in_en_time | text | 2020-11-19T07:26:32.687248+00:00 |
| fan2_ex_rpm | integer |  |
| fan1_ex_rpm | integer |  |
| fan2_ex_duty | integer |  |
| fan2_in_en | integer |  |
| fan_fault_flags | integer |  |
| exfan_ex_duty | double precision |  |
| exfan_ex_rpm_time | text |  |
| exfan_in_en | integer |  |
| fan_fm | jsonb | {'FAN_FM_MASK': 0, 'FAN_FM_FAULT': 0} |
| exfan_ex_en | integer |  |
| exfan_in_rpm_time | text |  |
| fan1_ex_duty | double precision |  |
| fan1_in_rpm | integer |  |
| exfan_ex_en_time | text |  |
| fan1_in_rpm_time | text |  |
| fan2_in_rpm_time | text |  |
| exfan_in_duty_time | text |  |
| fan1_ex_rpm_time | text |  |
| fan2_ex_duty_time | text |  |
| sw_fan_fault_mask | integer |  |
| fan2_in_duty | double precision |  |
| fan1_ex_duty_time | text |  |
| fan2_in_rpm | integer |  |
| fan2_in_duty_time | text |  |
| fan_fault_flags_time | text | 2020-11-19T07:26:32.275487+00:00 |
| exfan_in_en_time | text |  |
| exfan_ex_duty_time | text |  |
| fan_fault_mask | integer |  |
| fan2_ex_rpm_time | text |  |
| fan2_ex_en_time | text |  |
| fan1_ex_en | integer | 0 |
| fan2_in_en_time | text |  |
| exfan_in_duty | integer |  |
| sw_fan_fault_mask_time | text | 2020-11-19T07:26:32.275873+00:00 |
| fan1_in_duty_time | text |  |
| exfan_ex_rpm | integer |  |
| fan1_in_en | integer | 0 |
| fan_fault_mask_time | text | 2020-11-19T07:26:32.275686+00:00 |
| fan_fm_time | text | 2020-11-19T07:26:32.279325+00:00 |
| fan1_ex_en_time | text | 2020-11-19T07:26:32.893585+00:00 |
| fan2_ex_en | integer |  |
| fan1_in_duty | double precision |  |
| exfan_in_rpm | integer |  |
| time_recorded | timestamp with time zone | 2020-11-19 07:26:33.160953+00:00 |
| dos_instance | text | extern |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2020-11-19 07:26:33.282226+00:00 |
| row_status_user | text | desi_writer |

### aos_latest

Shared variable `AOS_LATEST`.

| Field | Type | Example |
|---|---|---|
| aos_latest | integer | 1 |
| aos_use | integer | 0 |
| dodx | double precision |  |
| dody | double precision |  |
| dodz | double precision |  |
| doxt | double precision |  |
| doyt | double precision |  |
| dodxerr | double precision |  |
| dodyerr | double precision |  |
| dodzerr | double precision |  |
| doxterr | double precision |  |
| doyterr | double precision |  |
| expid | integer |  |
| expframe | integer |  |
| exptime | double precision |  |
| nusedplus | integer |  |
| nusedminus | integer |  |
| nused | integer |  |
| mountaz | double precision |  |
| mountel | double precision |  |
| hexposx | double precision |  |
| hexposy | double precision |  |
| hexposz | double precision |  |
| hexposxtilt | double precision |  |
| hexposytilt | double precision |  |
| trustemp | double precision |  |
| pmirtemp | double precision |  |
| time_recorded | timestamp with time zone | 2020-11-25 23:15:52.154215+00:00 |
| dos_instance | text | donut |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2020-11-25 23:15:52.155553+00:00 |
| row_status_user | text | desi_writer |
| dox | double precision |  |
| doy | double precision |  |
| doz | double precision |  |
| doxtilt | double precision |  |
| doytilt | double precision |  |
| ft | double precision |  |
| last_updated | timestamp with time zone |  |

### aos_average

Shared variable `AOS_AVERAGE`.

| Field | Type | Example |
|---|---|---|
| aos_average | integer | 1 |
| aos_use | integer | 0 |
| nexp | integer |  |
| dodx | double precision |  |
| dody | double precision |  |
| dodz | double precision |  |
| doxt | double precision |  |
| doyt | double precision |  |
| dodxerr | double precision |  |
| dodyerr | double precision |  |
| dodzerr | double precision |  |
| doxterr | double precision |  |
| doyterr | double precision |  |
| expid | double precision |  |
| expframe | double precision |  |
| exptime | double precision |  |
| nusedplus | double precision |  |
| nusedminus | double precision |  |
| nused | double precision |  |
| mountaz | double precision |  |
| mountel | double precision |  |
| hexposx | double precision |  |
| hexposy | double precision |  |
| hexposz | double precision |  |
| hexposxtilt | double precision |  |
| hexposytilt | double precision |  |
| trustemp | double precision |  |
| pmirtemp | double precision |  |
| time_recorded | timestamp with time zone | 2020-11-25 23:15:52.162840+00:00 |
| dos_instance | text | donut |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2020-11-25 23:15:52.164012+00:00 |
| row_status_user | text | desi_writer |
| doytilt | double precision |  |
| doxtilt | double precision |  |
| dox | double precision |  |
| doy | double precision |  |
| doz | double precision |  |
| ft | double precision |  |
| last_updated | timestamp with time zone |  |
| tel_lut | ARRAY |  |

### adc_controllers

Shared variable `ADC_CONTROLLERS`.

| Field | Type | Example |
|---|---|---|
| adc_controllers | integer | 1 |
| status1 | text | STOPPED |
| angle1 | integer | 360 |
| rem_time1 | integer | 0 |
| status2 | text | STOPPED |
| angle2 | integer | 0 |
| rem_time2 | integer | 0 |
| nrev1 | integer | 0 |
| nrev2 | integer | 0 |
| time_recorded | timestamp with time zone | 2019-01-31 17:02:26.805223+00:00 |
| dos_instance | text | klaus |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2019-01-31 17:02:26.805970+00:00 |
| row_status_user | text | desi_writer |
| simulated | integer |  |
| home1 | integer |  |
| home2 | integer |  |
| drv_enbld1 | integer |  |
| drv_enbld2 | integer |  |

### hexapod_pos

Shared variable `HEXAPOD_POS`.

| Field | Type | Example |
|---|---|---|
| hexapod_pos | integer | 1 |
| pos | ARRAY | [0.0, 0.0, 0.0, 0.0, 0.0, 0.0] |
| time_recorded | timestamp with time zone | 2019-01-31 17:01:28.929537+00:00 |
| dos_instance | text | klaus |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2019-01-31 17:01:28.930172+00:00 |
| row_status_user | text | desi_writer |
| simulated | integer |  |

### donut_summary

Shared variable `DONUT_SUMMARY`.

| Field | Type | Example |
|---|---|---|
| donut_summary | integer | 1 |
| dodz | double precision | 16.166856815772746 |
| dodzerr | double precision | 4.564597140129798 |
| dodx | double precision | -410.26744550404203 |
| dody | double precision | -587.1660559839798 |
| doxt | double precision | -0.09857253848006042 |
| doyt | double precision | 5.495299202651837 |
| dodxerr | double precision | 42.7128592999797 |
| dodyerr | double precision | 28.72640051766016 |
| doxterr | double precision | 4.874279212314202 |
| doyterr | double precision | 5.068238842381899 |
| z4delta | double precision | 71.33314318422725 |
| z4thetax | double precision | -2740.4075249532593 |
| z4thetay | double precision | 4324.450958533495 |
| z4deltaerr | double precision | 4.564597140129798 |
| z4thetaxerr | double precision | 885.0570360802466 |
| z4thetayerr | double precision | 972.8228034198694 |
| z4meandeltabefore | double precision | 67.27890197134974 |
| z4rmsdeltabefore | double precision | 33.56111530995427 |
| z4meandeltaafter | double precision | 0.3454311019673688 |
| z4rmsdeltaafter | double precision | 10.174280490779795 |
| z5delta | double precision | 0.09178933781296872 |
| z5thetax | double precision | -0.050147062438552624 |
| z5thetay | double precision | -0.07058677606241 |
| z5deltaerr | double precision | 0.029236050593758285 |
| z5thetaxerr | double precision | 0.027363736513823362 |
| z5thetayerr | double precision | 0.03018752895361123 |
| z5meandeltabefore | double precision | 0.12829104033046998 |
| z5rmsdeltabefore | double precision | 0.12311342314754811 |
| z5meandeltaafter | double precision | 0.003905413940829184 |
| z5rmsdeltaafter | double precision | 0.10880409287204551 |
| z6delta | double precision | -0.0614045436903322 |
| z6thetax | double precision | 0.04399959923859947 |
| z6thetay | double precision | 0.07310343896052804 |
| z6deltaerr | double precision | 0.01885739716474783 |
| z6thetaxerr | double precision | 0.017464470789176404 |
| z6thetayerr | double precision | 0.019438961839507857 |
| z6meandeltabefore | double precision | -0.08643978592128101 |
| z6rmsdeltabefore | double precision | 0.08316492912084564 |
| z6meandeltaafter | double precision | -0.00012689909979586274 |
| z6rmsdeltaafter | double precision | 0.054161602368606024 |
| z7delta | double precision | 0.1148833490479847 |
| z7thetax | double precision | 0.03823628822353545 |
| z7thetay | double precision | -0.008688181727948564 |
| z7deltaerr | double precision | 0.004188504987901892 |
| z7thetaxerr | double precision | 0.0037244708741824848 |
| z7thetayerr | double precision | 0.004290849495148341 |
| z7meandeltabefore | double precision | 0.11216806380915378 |
| z7rmsdeltabefore | double precision | 0.055726286963696484 |
| z7meandeltaafter | double precision | 0.003573472602384665 |
| z7rmsdeltaafter | double precision | 0.022572920464287966 |
| z8delta | double precision | -0.08480305824919225 |
| z8thetax | double precision | -0.01617186018490977 |
| z8thetay | double precision | 0.042029508255224196 |
| z8deltaerr | double precision | 0.006934173109096238 |
| z8thetaxerr | double precision | 0.006216242429224318 |
| z8thetayerr | double precision | 0.007112331715599979 |
| z8meandeltabefore | double precision | -0.09140396207621718 |
| z8rmsdeltabefore | double precision | 0.06372852789333712 |
| z8meandeltaafter | double precision | 0.004375734693158583 |
| z8rmsdeltaafter | double precision | 0.02472618948314297 |
| nusedplus | integer | 10 |
| nusedminus | integer | 14 |
| nused | integer | 14 |
| hexpos | text | 1140.0,-480.0,58.5,-3.0,25.0,0.0 |
| hexposx | double precision | 1140.0 |
| hexposy | double precision | -480.0 |
| hexposz | double precision | 58.5 |
| hexposxtilt | double precision | -3.0 |
| hexposytilt | double precision | 25.0 |
| expid | integer | 52755 |
| expframe | integer | 2 |
| exptime | double precision | 30.0 |
| ifile | text | donut-00052755-0002.fits |
| mountaz | double precision | 271.227216 |
| mountel | double precision | 87.562751 |
| trustemp | double precision | 9.767 |
| pmirtemp | double precision | 7.662 |
| time_recorded | timestamp with time zone | 2020-11-25 23:17:45.070385+00:00 |
| dos_instance | text | donut |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2020-11-25 23:17:45.080722+00:00 |
| row_status_user | text | desi_writer |

### hexapod_trim

Shared variable `HEXAPOD_TRIM`.

| Field | Type | Example |
|---|---|---|
| hexapod_trim | integer | 1 |
| trim | ARRAY | [0.0, 0.0, 0.0, 0.0, 0.0, 0.0] |
| time_recorded | timestamp with time zone | 2019-01-31 17:01:26.829011+00:00 |
| dos_instance | text | klaus |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2019-01-31 17:01:26.829758+00:00 |
| row_status_user | text | desi_writer |
| simulated | integer |  |

### hexapod_hcustatus

Shared variable `HEXAPOD_HCUSTATUS`.

| Field | Type | Example |
|---|---|---|
| hexapod_hcustatus | integer | 1 |
| hcustatus | text | STA_CL |
| time_recorded | timestamp with time zone | 2019-01-31 17:01:28.923922+00:00 |
| dos_instance | text | klaus |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2019-01-31 17:01:28.924404+00:00 |
| row_status_user | text | desi_writer |

### ics_timing

Shared variable `ICS_TIMING`.

| Field | Type | Example |
|---|---|---|
| ics_timing | integer | 1 |
| guiderman_inverval | double precision |  |
| guiderman_cycle | double precision |  |
| time_recorded | timestamp with time zone | 2020-11-27 17:59:29.801914+00:00 |
| dos_instance | text | desi_20201127 |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2020-11-27 17:59:29.803043+00:00 |
| row_status_user | text | desi_writer |
| focusman_interval | double precision |  |
| focusman_cycle | double precision |  |
| skyman_cycle | double precision |  |
| skyman_interval | double precision |  |
| guiderib_assign | double precision | 11.907 |
| guiderib_sent | double precision |  |
| skyib_sent | double precision |  |
| skyib_assign | double precision |  |
| focusib_assign | double precision |  |
| focusib_sent | double precision |  |
| specib_sent | double precision |  |
| specib_assign | double precision |  |
| guider_assign | double precision |  |
| guider_sent | double precision |  |
| guiderman_throttle | double precision |  |
| skyman_throttle | double precision |  |
| focusman_throttle | double precision |  |
| guiderman_interval | double precision |  |
| guider_cycle | double precision |  |
| focusib_cycle | double precision |  |
| skyib_cycle | double precision |  |
| guiderib_cycle | double precision |  |

### gfa_boottime

Shared variable `GFA_BOOTTIME`.

| Field | Type | Example |
|---|---|---|
| gfa_boottime | integer | 1 |
| unit | integer | 8 |
| boottime | double precision | 39.428 |
| time_recorded | timestamp with time zone | 2020-12-01 16:15:57.085513+00:00 |
| dos_instance | text | desi_20201201 |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2020-12-01 16:15:57.085904+00:00 |
| row_status_user | text | desi_writer |

### cryostat_telemetry

Shared variable `CRYOSTAT_TELEMETRY`.

| Field | Type | Example |
|---|---|---|
| cryostat_telemetry | integer | 1 |
| va_def_gen | integer | 1 |
| va_red_in_cooldn | integer | 0 |
| va_red_in_ionic | integer | 0 |
| va_red_ready | integer | 0 |
| va_red_in_stop | integer | 0 |
| io_red_inter_fee | integer | 0 |
| va_red_def | integer | 1 |
| va_red_def_ip | integer | 0 |
| va_red_def_xpcde | integer | 0 |
| xp_red_rvs_k | double precision | 999.989990234375 |
| xp_red_rsp_k | double precision | 999.989990234375 |
| xp_red_rid | double precision | 999.989990234375 |
| xp_red_rvd | double precision | 999.989990234375 |
| xp_red_rva | double precision | 999.989990234375 |
| io_red_pt | double precision | 888.8800048828125 |
| va_red_ip_mb | double precision | 1.0288449779627395e-11 |
| io_red_tcp | double precision | 888.8800048828125 |
| io_red_tct | double precision | 888.8800048828125 |
| io_red_thh | double precision | 888.8800048828125 |
| va_blu_in_cooldn | integer | 0 |
| va_blu_in_ionic | integer | 0 |
| va_blu_ready | integer | 0 |
| va_blu_in_stop | integer | 0 |
| io_blu_inter_fee | integer | 0 |
| va_blu_def | integer | 0 |
| va_blu_def_ip | integer | 0 |
| va_blu_def_xpcde | integer | 1 |
| xp_blu_rvs_k | double precision | 999.989990234375 |
| xp_blu_rsp_k | double precision | 999.989990234375 |
| xp_blu_rid | double precision | 999.989990234375 |
| xp_blu_rvd | double precision | 999.989990234375 |
| xp_blu_rva | double precision | 999.989990234375 |
| io_blu_pt | double precision | 888.8800048828125 |
| va_blu_ip_mb | double precision | 1.0288449779627395e-11 |
| io_blu_tcp | double precision | 888.8800048828125 |
| io_blu_tct | double precision | 888.8800048828125 |
| io_blu_thh | double precision | 888.8800048828125 |
| va_nir_in_cooldn | integer | 0 |
| va_nir_in_ionic | integer | 0 |
| va_nir_ready | integer | 0 |
| va_nir_in_stop | integer | 0 |
| io_nir_inter_fee | integer | 0 |
| va_nir_def | integer | 0 |
| va_nir_def_ip | integer | 0 |
| va_nir_def_xpcde | integer | 1 |
| xp_nir_rvs_k | double precision | 999.989990234375 |
| xp_nir_rsp_k | double precision | 999.989990234375 |
| xp_nir_rid | double precision | 999.989990234375 |
| xp_nir_rvd | double precision | 999.989990234375 |
| xp_nir_rva | double precision | 999.989990234375 |
| io_nir_pt | double precision | 888.8800048828125 |
| va_nir_ip_mb | double precision | 1.0288449779627395e-11 |
| io_nir_tcp | double precision | 888.8800048828125 |
| io_nir_tct | double precision | 888.8800048828125 |
| io_nir_thh | double precision | 888.8800048828125 |
| time_recorded | timestamp with time zone | 2019-02-06 21:14:58.201011+00:00 |
| unit | integer | 0 |
| dos_instance | text | klaus |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2019-02-06 21:14:58.212879+00:00 |
| row_status_user | text | desi_writer |
| sp | integer |  |
| sm | integer |  |

### spectrographs_ccds

Shared variable `SPECTROGRAPHS_CCDS`.

| Field | Type | Example |
|---|---|---|
| spectrographs_ccds | integer | 1 |
| clk_mask | integer |  |
| dac_mask | integer |  |
| power_on | integer |  |
| ccd_idle | integer |  |
| time_recorded | timestamp with time zone | 2019-02-13 16:52:42.334602+00:00 |
| ccd | double precision |  |
| chassis | double precision |  |
| cpu | double precision |  |
| unit | integer | 0 |
| dos_instance | text | klaus |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2019-02-13 16:52:42.344657+00:00 |
| row_status_user | text | desi_writer |
| camera | text |  |
| vccd | integer |  |
| fee_interlock | integer |  |
| simulated | integer |  |

### spectrographs_sensors

Shared variable `SPECTROGRAPHS_SENSORS`.

| Field | Type | Example |
|---|---|---|
| spectrographs_sensors | integer | 1 |
| nir_camera_temp | double precision | 25.033 |
| nir_camera_humidity | double precision | 0.509 |
| red_camera_temp | double precision | 25.502 |
| red_camera_humidity | double precision | 0.675 |
| blue_camera_temp | double precision | 25.234 |
| blue_camera_humidity | double precision | 0.753 |
| bench_cryo_temp | double precision | 25.2 |
| bench_nir_temp | double precision | 25.15 |
| bench_coll_temp | double precision | 24.922 |
| ieb_temp | double precision | 24.997 |
| time_recorded | timestamp with time zone | 2019-02-13 16:52:43.886821+00:00 |
| unit | integer | 0 |
| dos_instance | text | klaus |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2019-02-13 16:52:45.069396+00:00 |
| row_status_user | text | desi_writer |
| simulated | integer |  |

### spectrographs_mechanisms

Shared variable `SPECTROGRAPHS_MECHANISMS`.

| Field | Type | Example |
|---|---|---|
| spectrographs_mechanisms | integer | 1 |
| status | text | READY |
| time_recorded | timestamp with time zone | 2019-02-13 16:52:45.053851+00:00 |
| unit | integer | 0 |
| dos_instance | text | klaus |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2019-02-13 16:52:45.061748+00:00 |
| row_status_user | text | desi_writer |
| hartmann_right | integer |  |
| hartmann_right_power | integer |  |
| hartmann_left_power | integer |  |
| hartmann_left | integer |  |
| exp_shutter | integer |  |
| exp_shutter_power | integer |  |
| exp_shutter_seal | integer |  |
| nir_shutter_seal | integer |  |
| nir_shutter_power | integer |  |
| nir_shutter | integer |  |
| wago | integer |  |
| illuminator | integer |  |
| simulated | integer |  |

### calibration_testslit

Shared variable `CALIBRATION_TESTSLIT`.

| Field | Type | Example |
|---|---|---|
| calibration_testslit | integer | 1 |
| temp | double precision | 24.8 |
| humidity | double precision | 38.0 |
| time_recorded | timestamp with time zone | 2019-02-15 14:02:48.468087+00:00 |
| dos_instance | text | klaus |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2019-02-15 14:02:48.468781+00:00 |
| row_status_user | text | desi_writer |
| hgar | integer |  |
| cd | integer |  |
| ne | integer |  |
| kr | integer |  |
| xe | integer |  |
| continuum1 | integer |  |
| continuum2 | integer |  |
| continuum3 | integer |  |

### shack_shack

Shared variable `SHACK_SHACK`.

| Field | Type | Example |
|---|---|---|
| shack_shack | integer | 1 |
| updated | text | 2019-02-19T21:11:14.695007 |
| time_recorded | timestamp with time zone | 2019-02-19 21:11:14.781120+00:00 |
| dos_instance | text | extern |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2019-02-19 21:11:14.782591+00:00 |
| row_status_user | text | desi_writer |
| sm1_power | integer |  |
| sm2_power | integer |  |
| sm3_power | integer |  |
| sm4_power | integer |  |
| sm5_power | integer |  |
| sm6_power | integer |  |
| sm7_power | integer |  |
| sm8_power | integer |  |
| sm9_power | integer |  |
| sm10_power | integer |  |
| wago | integer |  |
| sai_ssr | integer |  |
| sai_mr | integer |  |
| sai_power | integer |  |
| status | integer |  |
| illuminator | integer |  |
| wec | integer |  |

### shack_wec

Shared variable `SHACK_WEC`.

| Field | Type | Example |
|---|---|---|
| shack_wec | integer | 1 |
| ahu_unit | double precision | 0.0 |
| a_simulation | text | TRUE |
| room_pressure | double precision | 0.0 |
| space_temp1 | double precision | 0.0 |
| reheat_temp | double precision | 0.0 |
| updated | text | 2019-02-19T21:11:14.932671 |
| space_humidity | double precision | 0.0 |
| time_recorded | timestamp with time zone | 2019-02-19 21:11:14.946315+00:00 |
| dos_instance | text | extern |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2019-02-19 21:11:14.948080+00:00 |
| row_status_user | text | desi_writer |
| heater_output | double precision |  |
| space_temp2 | double precision |  |
| space_temp4 | double precision |  |
| space_temp_avg | double precision |  |
| space_temp3 | double precision |  |
| cooling_coil_temp | double precision |  |
| chilled_water_output | double precision |  |

### shack_wago

Shared variable `SHACK_WAGO`.

| Field | Type | Example |
|---|---|---|
| shack_wago | integer | 1 |
| purge_pressure | double precision | 9.3 |
| updated | text | 2019-02-19T21:11:14.695022 |
| seal_pressure | double precision | 19.77 |
| box_temp | double precision | 16.6 |
| time_recorded | timestamp with time zone | 2019-02-19 21:11:14.980251+00:00 |
| dos_instance | text | extern |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2019-02-19 21:11:14.981201+00:00 |
| row_status_user | text | desi_writer |

### performance_monitor

Shared variable `PERFORMANCE_MONITOR`.

| Field | Type | Example |
|---|---|---|
| performance_monitor | integer | 1 |
| status | integer | 1 |
| obsday | text | 20210410 |
| time_recorded | timestamp with time zone | 2021-04-11 14:43:19.196701+00:00 |
| dos_instance | text | desi_20210410 |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2021-04-11 14:43:19.197127+00:00 |
| row_status_user | text | desi_writer |
| last_updated | text |  |

### cifids_temperatures

Shared variable `CIFIDS_TEMPERATURES`.

| Field | Type | Example |
|---|---|---|
| cifids_temperatures | integer | 1 |
| t1 | double precision | 16.062 |
| t2 | double precision | 16.125 |
| t3 | double precision | 17.625 |
| t4 | double precision | 16.625 |
| t5 | double precision | 21.75 |
| time_recorded | timestamp with time zone | 2019-03-31 22:45:45.258478+00:00 |
| dos_instance | text | ci_20190331 |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2019-03-31 22:45:45.259125+00:00 |
| row_status_user | text | desi_writer |

### ics_memory

Shared variable `ICS_MEMORY`.

| Field | Type | Example |
|---|---|---|
| ics_memory | integer | 1 |
| role | text | GUIDE0 |
| memory | double precision | 111.56640625 |
| cpu | double precision | 0.0 |
| time_recorded | timestamp with time zone | 2021-05-18 18:42:20.318066+00:00 |
| dos_instance | text | desi_20210517 |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2021-05-18 18:42:20.318467+00:00 |
| row_status_user | text | desi_writer |
| free | double precision |  |

### contmonfp_telemetry

Shared variable `CONTMONFP_TELEMETRY`.

| Field | Type | Example |
|---|---|---|
| contmonfp_telemetry | integer | 1 |
| reflectivity_voltage | double precision | -0.42726173996925354 |
| scatter_voltage | double precision | -0.504182755947113 |
| temp_control_ok | integer | 0 |
| time_recorded | timestamp with time zone | 2021-06-10 16:14:32.310500+00:00 |
| dos_instance | text | ann |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2021-06-10 16:14:32.311139+00:00 |
| row_status_user | text | desi_writer |

### fiber_analysis

Shared variable `FIBER_ANALYSIS`.

| Field | Type | Example |
|---|---|---|
| date | date | 2021-06-03 |
| pos_id | text | M02691 |
| petal_id | integer | 4 |
| location | integer | 486 |
| hardstop | boolean | False |
| bad_scale | boolean | False |
| lodged | boolean | False |
| disabled_moving | boolean | False |
| autodisabled | boolean | False |
| concern | boolean | False |
| frozen | boolean | False |
| others | text |  |
| nautodis | integer | 0 |
| nlodged | integer | 0 |
| ndebounced | integer | 0 |
| ndebounced_fail | integer | 0 |
| ninterfere | integer | 0 |
| nfrozen | integer | 0 |
| nfrozen_unflag | integer | 0 |
| nlines | integer | 93 |
| nenabled | integer | 93 |
| nmoves | integer | 28 |
| nmoved | integer | 37 |
| nbigmoves | integer | 23 |
| nbigmoves_ok | integer | 17 |
| nbigmoves_up | integer | 6 |
| nbad_t | integer | 0 |
| nbad_p | integer | 0 |
| hard_t | double precision | 0.0 |
| scale_t_mean | double precision | 0.9873311519622803 |
| scale_t_err | double precision | 0.001998696243390441 |
| scale_t_rms | double precision | 0.0052880533039569855 |
| scale_t_max | double precision | 0.020191574469208717 |
| hard_p | double precision | 0.0 |
| scale_p_mean | double precision | 1.0100330114364624 |
| scale_p_err | double precision | 0.006959248799830675 |
| scale_p_rms | double precision | 0.01841244101524353 |
| scale_p_max | double precision | 0.03366166725754738 |
| time_recorded | timestamp with time zone |  |
| dos_instance | text | extern |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2021-07-08 01:02:52.670934+00:00 |
| row_status_user | text | desi_writer |

### guider_summary

Shared variable `GUIDER_SUMMARY`.

| Field | Type | Example |
|---|---|---|
| guider_summary | integer | 1 |
| duration | double precision | 82.79 |
| expid | integer | 7424 |
| seeing | double precision |  |
| frames | integer | 4 |
| meanx | double precision | 0.0 |
| meany | double precision | 0.0 |
| meanx2 | double precision | 0.0 |
| meany2 | double precision | 0.0 |
| meanxy | double precision | 0.0 |
| maxx | double precision | 0.0 |
| maxy | double precision | 0.0 |
| time_recorded | timestamp with time zone | 2019-04-18 02:43:47.150035+00:00 |
| dos_instance | text | ci_20190417 |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2019-04-18 02:43:47.150767+00:00 |
| row_status_user | text | desi_writer |

### environmentmonitor_elnino

Shared variable `ENVIRONMENTMONITOR_ELNINO`.

| Field | Type | Example |
|---|---|---|
| environmentmonitor_elnino | integer | 1 |
| elnino_timestamp | text | 2021-11-24 11:02:05 |
| zp_adu_per_s_desi | double precision | 13.640887816050183 |
| sky_adu_per_s_desi | double precision | 214.03095703125 |
| zp_adu_per_s | double precision | 14.19357525534133 |
| sky_adu_per_s | double precision | 213.381103515625 |
| flag | integer | 0 |
| mjd_obs | double precision | 59542.460211 |
| time_recorded | timestamp with time zone | 2021-11-24 19:42:33.829888+00:00 |
| dos_instance | text | extern |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2021-11-24 19:42:33.838167+00:00 |
| row_status_user | text | desi_writer |
| between_twilight | integer |  |

### petalman_times

Shared variable `PETALMAN_TIMES`.

| Field | Type | Example |
|---|---|---|
| petalman_times | integer | 1 |
| handlefvcfeedback_after_blind | double precision |  |
| prepareformove_blind | double precision |  |
| executemove_blind | double precision |  |
| handlefvcfeedback_after_corr | double precision |  |
| prepareformove_corr | double precision |  |
| executemove_corr | double precision | 28.2491 |
| expid | integer | 115150 |
| iteration | integer | 1 |
| time_recorded | timestamp with time zone | 2021-12-23 01:24:41.720067+00:00 |
| dos_instance | text | desi_20211222 |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2021-12-23 01:24:41.723283+00:00 |
| row_status_user | text | desi_writer |

### ocs_slew

Shared variable `OCS_SLEW`.

| Field | Type | Example |
|---|---|---|
| ocs_slew | integer | 1 |
| slewtime | double precision | 0.536 |
| slewangl | double precision |  |
| moonsep | double precision |  |
| time_recorded | timestamp with time zone | 2022-01-04 01:15:08.079777+00:00 |
| dos_instance | text | desi_20220103 |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2022-01-04 01:15:08.080359+00:00 |
| row_status_user | text | desi_writer |

### ocs_intexptime

Shared variable `OCS_INTEXPTIME`.

| Field | Type | Example |
|---|---|---|
| ocs_intexptime | integer | 1 |
| intexptime | double precision | 157.666 |
| time_recorded | timestamp with time zone | 2022-01-04 01:38:45.658723+00:00 |
| dos_instance | text | desi_20220103 |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2022-01-04 01:38:45.659432+00:00 |
| row_status_user | text | desi_writer |

### gfa_ptl_sensors

Shared variable `GFA_PTL-SENSORS`.

| Field | Type | Example |
|---|---|---|
| gfa_ptl_sensors | integer | 1 |
| gfa_fan_in_pwm | double precision | 0.0 |
| gfa_fan_out_pwm | double precision | 0.0 |
| gfa_fan_in_tach | integer | 0 |
| gfa_fan_out_tach | integer | 0 |
| gfatime | text | 2022-06-14T15:13:17.505775 |
| pbox_temp_sensor | double precision |  |
| fpp_temp_sensor_1 | double precision |  |
| fpp_temp_sensor_2 | double precision |  |
| fpp_temp_sensor_3 | double precision |  |
| fpp_temp_sensor_13 | double precision |  |
| fpp_temp_sensor_7 | double precision |  |
| fpp_temp_sensor_11 | double precision |  |
| fpp_temp_sensor_6 | double precision |  |
| fpp_temp_sensor_12 | double precision |  |
| fpp_temp_sensor_8 | double precision |  |
| fpp_temp_sensor_4 | double precision |  |
| fpp_temp_sensor_10 | double precision |  |
| fpp_temp_sensor_9 | double precision |  |
| fpp_temp_sensor_5 | double precision |  |
| gxb_temp_sensor | double precision |  |
| temptime | text | 2022-06-14T15:13:14.456632 |
| gxbcur | double precision |  |
| gxbtime | text |  |
| pcid | integer | 0 |
| time | text | 2022-06-14T15:13:17.506749 |
| simulated | integer | 0 |
| time_recorded | timestamp with time zone | 2022-06-14 15:13:17.534774+00:00 |
| dos_instance | text | extern |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2022-06-14 15:13:17.549899+00:00 |
| row_status_user | text | desi_writer |

### gfa_ptl_status

Shared variable `GFA_PTL-STATUS`.

| Field | Type | Example |
|---|---|---|
| gfa_ptl_status | integer | 1 |
| gfa_ovrtmp | integer | 0 |
| gfa_fan_in_en | integer | 0 |
| gfa_fan_out_en | integer | 0 |
| pcid | integer | 0 |
| time | text | 2022-06-14T15:13:17.509106 |
| gfapwr_en | text | 0 |
| tec_ctrl | text | 0 |
| fxc_okay | text | 1 |
| ccdbiasenabled | integer | 0 |
| ccdbias | integer | 0 |
| telemetryfault | integer | 0 |
| status | jsonb | {} |
| simulated | integer | 0 |
| time_recorded | timestamp with time zone | 2022-06-14 15:13:17.581603+00:00 |
| dos_instance | text | extern |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2022-06-14 15:13:17.591096+00:00 |
| row_status_user | text | desi_writer |

### gfa_ptl_powerup

Shared variable `GFA_PTL-POWERUP`.

| Field | Type | Example |
|---|---|---|
| gfa_ptl_powerup | integer | 1 |
| time | text | 2022-06-14T15:13:08.434214 |
| pcid | integer | 0 |
| thresholds | jsonb | {'CURR_GXB_WARN': 100, 'TACH_FAN_WARN': 2000, 'TE... |
| status | jsonb | {} |
| network_status | jsonb | {'is_up': True, 'is_alive': True, 'was_lost': Fal... |
| simulated | integer | 0 |
| time_recorded | timestamp with time zone | 2022-06-14 15:13:08.484375+00:00 |
| dos_instance | text | extern |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2022-06-14 15:13:08.493435+00:00 |
| row_status_user | text | desi_writer |

### ocs_astrometry

Shared variable `OCS_ASTROMETRY`.

| Field | Type | Example |
|---|---|---|
| ocs_astrometry | integer | 1 |
| astrometry | text |  |
| time_recorded | timestamp with time zone | 2022-10-26 15:09:28.368624+00:00 |
| dos_instance | text | desi_20221025 |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2022-10-26 15:09:28.369512+00:00 |
| row_status_user | text | desi_writer |
| matched_stars | integer |  |
| gfas_in_solution | integer |  |
| astro_rmsx | double precision |  |
| astro_rmsy | double precision |  |
| astro_fwhm | double precision |  |
| astro_magoff | double precision |  |
| astro_status | integer |  |
| expid | integer |  |
| found_stars | integer |  |
| offsetx | double precision |  |
| offsety | double precision |  |

### spottrack_camerastatus

Shared variable `SPOTTRACK_CAMERASTATUS`.

| Field | Type | Example |
|---|---|---|
| spottrack_camerastatus | integer | 1 |
| open | integer | 1 |
| reset | integer | 1 |
| expose | integer | 0 |
| idle | integer | 1 |
| process | integer | 0 |
| error | integer | 0 |
| last_updated | text | 2023-02-14T23:28:55.678930 |
| camera_tmp | double precision | 23.0 |
| sensor_tmp | double precision | -9.9 |
| pwrsuppy_tmp | double precision | 13.0 |
| receive_cnt | integer | 0 |
| rec_state | text | STOP |
| image_rate | double precision | 0.2 |
| miss_count | integer | 0 |
| spot_count | integer | 0 |
| cluster_count | integer | 0 |
| track_count | integer | 0 |
| act_exptime | integer | 0 |
| expid | integer | 0 |
| expframe | integer | 0 |
| time_recorded | timestamp with time zone | 2023-02-14 23:28:55.684679+00:00 |
| dos_instance | text | extern |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2023-02-14 23:28:55.686158+00:00 |
| row_status_user | text | desi_writer |
| execution_status | text |  |

### frontilluminator_fioutlets

Shared variable `FRONTILLUMINATOR_FIOUTLETS`.

| Field | Type | Example |
|---|---|---|
| frontilluminator_fioutlets | integer | 1 |
| time_recorded | timestamp with time zone | 2023-08-03 03:05:12.725474+00:00 |
| dos_instance | text | extern |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2023-08-03 03:05:12.733007+00:00 |
| row_status_user | text | desi_writer |
| petal5 | integer |  |
| petal0 | integer |  |

### lux_telemetry

Shared variable `LUX_TELEMETRY`.

| Field | Type | Example |
|---|---|---|
| lux_telemetry | integer | 1 |
| time_recorded | timestamp with time zone | 2023-12-27 20:40:59+00:00 |
| dos_instance | text | extern |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2023-12-27 20:40:59.821066+00:00 |
| row_status_user | text | desi_writer |
| shack | jsonb |  |
| dome | jsonb |  |

### nfs_requesttime

Shared variable `NFS_REQUESTTIME`.

| Field | Type | Example |
|---|---|---|
| nfs_requesttime | integer | 1 |
| requesttime | double precision | 0.038 |
| time_recorded | timestamp with time zone | 2024-02-26 00:52:36.267245+00:00 |
| dos_instance | text | desi_20240225 |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2024-02-26 00:52:36.270451+00:00 |
| row_status_user | text | desi_writer |
| tile | integer |  |
| program | text |  |

### spectrographs_cpuload

Shared variable `SPECTROGRAPHS_CPULOAD`.

| Field | Type | Example |
|---|---|---|
| spectrographs_cpuload | integer | 1 |
| unit | text | CCDS5R |
| cpu | double precision | 48.2 |
| virtmem | double precision | 7.8 |
| time_recorded | timestamp with time zone | 2024-04-03 14:29:08.440632+00:00 |
| dos_instance | text | extern |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2024-04-03 14:29:08.458449+00:00 |
| row_status_user | text | desi_writer |
| sp | integer |  |
| sm | integer |  |
| ccd | text |  |

### ocs_nfsconstraints

Shared variable `OCS_NFSCONSTRAINTS`.

| Field | Type | Example |
|---|---|---|
| ocs_nfsconstraints | integer | 1 |
| elrange | ARRAY |  |
| azrange | ARRAY |  |
| static_fa_only | integer |  |
| expid | integer |  |
| time_recorded | timestamp with time zone | 2024-12-16 20:03:45.358968+00:00 |
| dos_instance | text | desi_20241215 |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2024-12-16 20:03:45.359719+00:00 |
| row_status_user | text | desi_writer |

### spectrographs_actuators

Shared variable `SPECTROGRAPHS_ACTUATORS`.

| Field | Type | Example |
|---|---|---|
| spectrographs_actuators | integer | 1 |
| focus_serial | integer | 26250023 |
| wavetilt_serial | integer | 26250070 |
| fibertilt_serial | integer | 26250080 |
| focus_initialized | integer | 0 |
| wavetilt_initialized | integer | 0 |
| fibertilt_initialized | integer | 0 |
| focus_homed | integer | 0 |
| wavetilt_homed | integer | 0 |
| fibertilt_homed | integer | 0 |
| default_focus_posmm | double precision | 9.295 |
| default_wavetilt_posmm | double precision | 6.807 |
| default_fibertilt_posmm | double precision | 10.891 |
| focus_posmm | double precision | 9.295 |
| wavetilt_posmm | double precision | 6.807 |
| fibertilt_posmm | double precision | 10.891 |
| message | text |  |
| updated | text | 2025-01-14T15:19:30.084423 |
| simulated | integer | 0 |
| time_recorded | timestamp with time zone | 2025-01-14 15:19:30.089002+00:00 |
| unit | integer | 7 |
| specid | integer | 8 |
| dos_instance | text | extern |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2025-01-14 15:19:30.128435+00:00 |
| row_status_user | text | desi_writer |
| status | integer |  |
| usb | integer |  |
| motors | integer |  |
| collimator_power | integer |  |
| focus_usb | text |  |
| wavetilt_usb | text |  |
| fibertilt_usb | text |  |

### calibration_calpduswitch

Shared variable `CALIBRATION_CALPDUSWITCH`.

| Field | Type | Example |
|---|---|---|
| calibration_calpduswitch | integer | 1 |
| calpduswitch | text |  |
| time_recorded | timestamp with time zone | 2025-08-12 18:29:04.113326+00:00 |
| dos_instance | text | desi_20250811 |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2025-08-12 18:29:04.114414+00:00 |
| row_status_user | text | desi_writer |
| state | integer |  |

### calibration_booted

Shared variable `CALIBRATION_BOOTED`.

| Field | Type | Example |
|---|---|---|
| calibration_booted | integer | 1 |
| time_recorded | timestamp with time zone | 2025-08-15 19:21:47.331157+00:00 |
| dos_instance | text | desi_20250814 |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2025-08-15 19:21:47.331735+00:00 |
| row_status_user | text | desi_writer |
| state | integer |  |

### pc_ptltcan

Shared variable `PC_PTLTCAN`.

| Field | Type | Example |
|---|---|---|
| pc_ptltcan | integer | 1 |
| pctime | timestamp with time zone | 2025-09-10 02:15:51.533155+00:00 |
| pcid | integer | 7 |
| simulated | integer | 0 |
| rec | jsonb | {'can30': -1, 'can31': -1, 'can32': -1, 'can33': ... |
| tec | jsonb | {'can30': -1, 'can31': -1, 'can32': -1, 'can33': ... |
| time_recorded | timestamp with time zone | 2025-09-10 02:15:51.591428+00:00 |
| dos_instance | text | extern |
| row_status | text | M |
| row_status_time | timestamp with time zone | 2025-09-10 02:15:51.604396+00:00 |
| row_status_user | text | desi_writer |

### Requested tables not found in this snapshot

These were in the collection list but returned no columns -- they don't exist in the `telemetry` schema as named (e.g. per-GFA-camera `guideN`/`focusN` tables, or renamed/retired tables):

`guide0_telemetry`, `guide2_telemetry`, `guide4_telemetry`, `guide5_telemetry`, `guide7_telemetry`, `guide9_telemetry`, `focus1_telemetry`, `focus3_telemetry`, `focus6_telemetry`, `focus8_telemetry`, `gfa_memory`, `ib_memory`

<!-- END telemetry appendix -->
