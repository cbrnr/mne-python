#
# Authors: The MNE-Python contributors.
# License: BSD-3-Clause
# Copyright the MNE-Python contributors.

from datetime import datetime, timezone
from pathlib import Path
from shutil import copyfile

import numpy as np
import pytest
from numpy.testing import assert_allclose, assert_array_equal

from mne._fiff.constants import FIFF
from mne._fiff.tag import _loc_to_coil_trans
from mne.annotations import events_from_annotations, read_annotations
from mne.bem import _fit_sphere
from mne.datasets import testing
from mne.event import find_events
from mne.io.bti import read_raw_bti
from mne.io.curry import read_raw_curry
from mne.io.curry.curry import (
    FILE_EXTENSIONS,
    _get_curry_file_structure,
    _get_curry_version,
    _read_events_curry,
)
from mne.io.edf import read_raw_bdf
from mne.io.tests.test_raw import _test_raw_reader
from mne.utils import catch_logging

data_dir = testing.data_path(download=False)
curry_dir = data_dir / "curry"
bdf_file = data_dir / "BDF" / "test_bdf_stim_channel.bdf"
bti_rfDC_file = data_dir / "BTi" / "erm_HFH" / "c,rfDC"
curry7_rfDC_file = curry_dir / "c,rfDC Curry 7.dat"
curry8_rfDC_file = curry_dir / "c,rfDC Curry 8.cdt"
curry7_bdf_file = curry_dir / "test_bdf_stim_channel Curry 7.dat"
curry7_bdf_ascii_file = curry_dir / "test_bdf_stim_channel Curry 7 ASCII.dat"
curry8_bdf_file = curry_dir / "test_bdf_stim_channel Curry 8.cdt"
curry8_bdf_ascii_file = curry_dir / "test_bdf_stim_channel Curry 8 ASCII.cdt"
missing_event_file = curry_dir / "test_sfreq_0.dat"
Ref_chan_omitted_file = curry_dir / "Ref_channel_omitted Curry7.dat"
Ref_chan_omitted_reordered_file = curry_dir / "Ref_channel_omitted reordered Curry7.dat"


@pytest.fixture(scope="session")
def bdf_curry_ref():
    """Return a view of the reference bdf used to create the curry files."""
    raw = read_raw_bdf(bdf_file, preload=True).drop_channels(["Status"])
    return raw


@testing.requires_testing_data
@pytest.mark.parametrize(
    "fname,tol",
    [
        pytest.param(curry7_bdf_file, 1e-7, id="curry 7"),
        pytest.param(curry8_bdf_file, 1e-7, id="curry 8"),
        pytest.param(curry7_bdf_ascii_file, 1e-4, id="curry 7 ascii"),
        pytest.param(curry8_bdf_ascii_file, 1e-4, id="curry 8 ascii"),
    ],
)
@pytest.mark.parametrize("preload", [True, False])
def test_read_raw_curry(fname, tol, preload, bdf_curry_ref):
    """Test reading CURRY files."""
    raw = read_raw_curry(fname, preload=preload)

    assert hasattr(raw, "_data") == preload
    assert raw.n_times == bdf_curry_ref.n_times
    assert raw.info["sfreq"] == bdf_curry_ref.info["sfreq"]

    for field in ["kind", "ch_name"]:
        assert_array_equal(
            [ch[field] for ch in raw.info["chs"]],
            [ch[field] for ch in bdf_curry_ref.info["chs"]],
        )

    assert_allclose(raw.get_data(verbose="error"), bdf_curry_ref.get_data(), atol=tol)

    picks, start, stop = ["C3", "C4"], 200, 800
    assert_allclose(
        raw.get_data(picks=picks, start=start, stop=stop, verbose="error"),
        bdf_curry_ref.get_data(picks=picks, start=start, stop=stop),
        rtol=tol,
    )
    assert raw.info["dev_head_t"] is None


@testing.requires_testing_data
@pytest.mark.parametrize(
    "fname",
    [
        pytest.param(curry7_bdf_file, id="curry 7"),
        pytest.param(curry8_bdf_file, id="curry 8"),
        pytest.param(curry7_bdf_ascii_file, id="curry 7 ascii"),
        pytest.param(curry8_bdf_ascii_file, id="curry 8 ascii"),
    ],
)
def test_read_raw_curry_test_raw(fname):
    """Test read_raw_curry with _test_raw_reader."""
    _test_raw_reader(read_raw_curry, fname=fname)


# These values taken from a different recording but allow us to test
# using our existing filres

HPI_CONTENT = """\
FileVersion:	804
NumCoils:	10

0	1	-50.67	50.98	133.15	0.006406		1	46.45	51.51	143.15	0.006789		1	39.38	-26.67	155.51	0.008034		1	-36.72	-39.95	142.83	0.007700		1	1.61	16.95	172.76	0.001788		0	0.00	0.00	0.00	0.000000		0	0.00	0.00	0.00	0.000000		0	0.00	0.00	0.00	0.000000		0	0.00	0.00	0.00	0.000000		0	0.00	0.00	0.00	0.000000
"""  # noqa: E501


LM_CONTENT = """

LANDMARKS_MAG1 START
   ListDescription      = functional landmark positions
   ListUnits            = mm
   ListNrColumns        =  3
   ListNrRows           =  8
   ListNrTimepts        =  1
   ListNrBlocks         =  1
   ListBinary           =  0
   ListType             =  1
   ListTrafoType        =  1
   ListGridType         =  2
   ListFirstColumn      =  1
   ListIndexMin         = -1
   ListIndexMax         = -1
   ListIndexAbsMax      = -1
LANDMARKS_MAG1 END

LANDMARKS_MAG1 START_LIST	# Do not edit!
  75.4535	 5.32907e-15	 2.91434e-16
  1.42109e-14	-75.3212	 9.71445e-16
 -74.4568	-1.42109e-14	 2.51188e-15
 -59.7558	 35.5804	 66.822
  43.15	 43.4107	 78.0027
  38.8415	-41.1884	 81.9941
 -36.683	-59.5119	 66.4338
 -1.07259	-1.88025	 103.747
LANDMARKS_MAG1 END_LIST

LM_INDICES_MAG1 START
   ListDescription      = functional landmark PAN info
   ListUnits            =
   ListNrColumns        =  1
   ListNrRows           =  3
   ListNrTimepts        =  1
   ListNrBlocks         =  1
   ListBinary           =  0
   ListType             =  0
   ListTrafoType        =  0
   ListGridType         =  2
   ListFirstColumn      =  1
   ListIndexMin         = -1
   ListIndexMax         = -1
   ListIndexAbsMax      = -1
LM_INDICES_MAG1 END

LM_INDICES_MAG1 START_LIST	# Do not edit!
  2
  1
  3
LM_INDICES_MAG1 END_LIST

LM_REMARKS_MAG1 START
   ListDescription      = functional landmark labels
   ListUnits            =
   ListNrColumns        =  40
   ListNrRows           =  8
   ListNrTimepts        =  1
   ListNrBlocks         =  1
   ListBinary           =  0
   ListType             =  5
   ListTrafoType        =  0
   ListGridType         =  2
   ListFirstColumn      =  1
   ListIndexMin         = -1
   ListIndexMax         = -1
   ListIndexAbsMax      = -1
LM_REMARKS_MAG1 END

LM_REMARKS_MAG1 START_LIST	# Do not edit!
Left ear
Nasion
Right ear
HPI1
HPI2
HPI3
HPI4
HPI5
LM_REMARKS_MAG1 END_LIST

"""

WANT_TRANS = np.array(
    [
        [0.99729224, -0.07353067, -0.00119791, 0.00126953],
        [0.07319243, 0.99085848, 0.11332405, 0.02670814],
        [-0.00714583, -0.11310488, 0.99355736, 0.04721836],
        [0.0, 0.0, 0.0, 1.0],
    ]
)


@testing.requires_testing_data
@pytest.mark.parametrize(
    "fname,tol",
    [
        pytest.param(curry7_rfDC_file, 1e-6, id="curry 7"),
        pytest.param(curry8_rfDC_file, 1e-3, id="curry 8"),
    ],
)
@pytest.mark.parametrize("mock_dev_head_t", [True, False])
def test_read_raw_curry_rfDC(fname, tol, mock_dev_head_t, tmp_path):
    """Test reading CURRY files."""
    if mock_dev_head_t:
        if "Curry 7" in fname.name:  # not supported yet
            return
        # copy files to tmp_path
        for ext in (".cdt", ".cdt.dpa"):
            src = fname.with_suffix(ext)
            dst = tmp_path / fname.with_suffix(ext).name
            copyfile(src, dst)
            if ext == ".cdt.dpa":
                with open(dst, "a") as fid:
                    fid.write(LM_CONTENT)
        fname = tmp_path / fname.name
        with open(fname.with_suffix(fname.suffix + ".hpi"), "w") as fid:
            fid.write(HPI_CONTENT)

    # check data
    bti_rfDC = read_raw_bti(pdf_fname=bti_rfDC_file, head_shape_fname=None)
    with catch_logging() as log:
        raw = read_raw_curry(fname, verbose=True)
    log = log.getvalue()
    if mock_dev_head_t:
        assert "Composing device" in log
    else:
        assert "Leaving device" in log
        assert "no landmark" in log

    # test on the eeg chans, since these were not renamed by curry
    eeg_names = [
        ch["ch_name"] for ch in raw.info["chs"] if ch["kind"] == FIFF.FIFFV_EEG_CH
    ]

    assert_allclose(raw.get_data(eeg_names), bti_rfDC.get_data(eeg_names), rtol=tol)
    assert bti_rfDC.info["dev_head_t"] is not None  # XXX probably a BTI bug
    if mock_dev_head_t:
        assert raw.info["dev_head_t"] is not None
        assert_allclose(raw.info["dev_head_t"]["trans"], WANT_TRANS, atol=1e-5)
    else:
        assert raw.info["dev_head_t"] is None

    # check that most MEG sensors are approximately oriented outward from
    # the device origin
    n_meg = n_eeg = n_other = 0
    pos = list()
    nn = list()
    for ch in raw.info["chs"]:
        if ch["kind"] == FIFF.FIFFV_MEG_CH:
            assert ch["coil_type"] == FIFF.FIFFV_COIL_CTF_GRAD
            t = _loc_to_coil_trans(ch["loc"])
            pos.append(t[:3, 3])
            nn.append(t[:3, 2])
            assert_allclose(np.linalg.norm(nn[-1]), 1.0)
            n_meg += 1
        elif ch["kind"] == FIFF.FIFFV_EEG_CH:
            assert ch["coil_type"] == FIFF.FIFFV_COIL_EEG
            n_eeg += 1
        else:
            assert ch["coil_type"] == FIFF.FIFFV_COIL_NONE
            n_other += 1
    assert n_meg == 148
    assert n_eeg == 31
    assert n_other == 15
    pos = np.array(pos)
    nn = np.array(nn)
    rad, origin = _fit_sphere(pos)
    assert 0.11 < rad < 0.13
    pos -= origin
    pos /= np.linalg.norm(pos, axis=1, keepdims=True)
    angles = np.abs(np.rad2deg(np.arccos((pos * nn).sum(-1))))
    assert (angles < 20).sum() > 100


@testing.requires_testing_data
@pytest.mark.parametrize(
    "fname",
    [
        pytest.param(curry7_bdf_file, id="curry 7"),
        pytest.param(curry8_bdf_file, id="curry 8"),
    ],
)
def test_read_events_curry_are_same_as_bdf(fname):
    """Test events from curry annotations recovers the right events."""
    EVENT_ID = {str(ii): ii for ii in range(5)}
    REF_EVENTS = find_events(read_raw_bdf(bdf_file, preload=True))

    raw = read_raw_curry(fname)
    events, _ = events_from_annotations(raw, event_id=EVENT_ID)
    assert_allclose(events, REF_EVENTS)
    assert raw.info["dev_head_t"] is None


@testing.requires_testing_data
def test_check_missing_files():
    """Test checking for missing curry files (smoke test)."""
    invalid_fname = "/invalid/path/name.xy"

    with pytest.raises(OSError, match="file type .*? must end with"):
        _read_events_curry(invalid_fname)

    with pytest.raises(FileNotFoundError, match="does not exist"):
        _get_curry_file_structure(invalid_fname)

    with pytest.raises(FileNotFoundError, match="files cannot be found"):
        _get_curry_file_structure(missing_event_file, required=["info", "events"])


def _mock_info_file(src, dst, sfreq, time_step):
    with open(src) as in_file, open(dst, "w") as out_file:
        for line in in_file:
            if "SampleFreqHz" in line:
                out_file.write(line.replace("500", str(sfreq)))
            elif "SampleTimeUsec" in line:
                out_file.write(line.replace("2000", str(time_step)))
            else:
                out_file.write(line)


@pytest.fixture(
    params=[
        pytest.param(dict(sfreq=500, time_step=0), id="correct sfreq"),
        pytest.param(dict(sfreq=0, time_step=2000), id="correct time_step"),
        pytest.param(dict(sfreq=500, time_step=2000), id="both correct"),
        pytest.param(
            dict(sfreq=0, time_step=0),
            id="both 0",
            marks=pytest.mark.xfail(raises=ValueError),
        ),
        pytest.param(
            dict(sfreq=500, time_step=42),
            id="mismatch",
            marks=pytest.mark.xfail(raises=ValueError),
        ),
    ]
)
def sfreq_testing_data(tmp_path, request):
    """Generate different sfreq, time_step scenarios to be tested."""
    sfreq, time_step = request.param["sfreq"], request.param["time_step"]

    # create dummy empty files for 'dat' and 'rs3'
    for fname in ["curry.dat", "curry.rs3"]:
        open(tmp_path / fname, "a").close()

    _mock_info_file(
        src=curry7_bdf_file.with_suffix(".dap"),
        dst=tmp_path / "curry.dap",
        sfreq=sfreq,
        time_step=time_step,
    )
    _mock_info_file(
        src=curry7_bdf_file.with_suffix(".rs3"),
        dst=tmp_path / "curry.rs3",
        sfreq=sfreq,
        time_step=time_step,
    )
    return tmp_path / "curry.dat"


@testing.requires_testing_data
def test_sfreq(sfreq_testing_data):
    """Test sfreq and time_step."""
    raw = read_raw_curry(sfreq_testing_data, preload=False)
    assert raw.info["sfreq"] == 500


@testing.requires_testing_data
@pytest.mark.parametrize(
    "fname",
    [
        pytest.param(curry_dir / "test_bdf_stim_channel Curry 7.cef", id="7"),
        pytest.param(curry_dir / "test_bdf_stim_channel Curry 8.cdt.cef", id="8"),
        pytest.param(
            curry_dir / "test_bdf_stim_channel Curry 7 ASCII.cef", id="7 ascii"
        ),
        pytest.param(
            curry_dir / "test_bdf_stim_channel Curry 8 ASCII.cdt.cef", id="8 ascii"
        ),
    ],
)
def test_read_curry_annotations(fname):
    """Test reading for Curry events file."""
    EXPECTED_ONSET = [
        0.484,
        0.486,
        0.62,
        0.622,
        1.904,
        1.906,
        3.212,
        3.214,
        4.498,
        4.5,
        5.8,
        5.802,
        7.074,
        7.076,
        8.324,
        8.326,
        9.58,
        9.582,
    ]
    EXPECTED_DURATION = np.zeros_like(EXPECTED_ONSET)
    EXPECTED_DESCRIPTION = [
        "4",
        "50000",
        "2",
        "50000",
        "1",
        "50000",
        "1",
        "50000",
        "1",
        "50000",
        "1",
        "50000",
        "1",
        "50000",
        "1",
        "50000",
        "1",
        "50000",
    ]

    annot = read_annotations(fname, sfreq="auto")

    assert annot.orig_time is None
    assert_array_equal(annot.onset, EXPECTED_ONSET)
    assert_array_equal(annot.duration, EXPECTED_DURATION)
    assert_array_equal(annot.description, EXPECTED_DESCRIPTION)


def _get_read_annotations_mock_info(name_part, mock_dir):
    original, modified = dict(), dict()

    original["event"] = curry_dir / ("test_bdf_stim_channel " + name_part)
    original["base"], ext = str(original["event"]).split(".", maxsplit=1)
    original["base"] = Path(original["base"])
    version = _get_curry_version(ext)
    original["info"] = original["base"].with_suffix(FILE_EXTENSIONS[version]["info"])

    modified["base"] = mock_dir / "curry"
    modified["event"] = modified["base"].with_suffix(
        FILE_EXTENSIONS[version]["events_cef"]
    )
    modified["info"] = modified["base"].with_suffix(FILE_EXTENSIONS[version]["info"])

    return original, modified


@testing.requires_testing_data
@pytest.mark.parametrize(
    "name_part",
    [
        pytest.param("7.cef", id="7"),
        pytest.param("8.cdt.cef", id="8"),
        pytest.param("7 ASCII.cef", id="7 (ascii)"),
        pytest.param("8 ASCII.cdt.cef", id="8 (ascii)"),
    ],
)
def test_read_curry_annotations_using_mocked_info(tmp_path, name_part):
    """Test reading for Curry events file."""
    EXPECTED_ONSET = [
        0.484,
        0.486,
        0.62,
        0.622,
        1.904,
        1.906,
        3.212,
        3.214,
        4.498,
        4.5,
        5.8,
        5.802,
        7.074,
        7.076,
        8.324,
        8.326,
        9.58,
        9.582,
    ]
    EXPECTED_DURATION = np.zeros_like(EXPECTED_ONSET)
    EXPECTED_DESCRIPTION = [
        "4",
        "50000",
        "2",
        "50000",
        "1",
        "50000",
        "1",
        "50000",
        "1",
        "50000",
        "1",
        "50000",
        "1",
        "50000",
        "1",
        "50000",
        "1",
        "50000",
    ]

    original, fname = _get_read_annotations_mock_info("Curry " + name_part, tmp_path)
    copyfile(src=original["event"], dst=fname["event"])

    _msg = "required files cannot be found"
    with pytest.raises(FileNotFoundError, match=_msg):
        read_annotations(fname["event"], sfreq="auto")

    _mock_info_file(src=original["info"], dst=fname["info"], sfreq=0, time_step=2000)

    annot = read_annotations(fname["event"], sfreq="auto")

    assert annot.orig_time is None
    assert_array_equal(annot.onset, EXPECTED_ONSET)
    assert_array_equal(annot.duration, EXPECTED_DURATION)
    assert_array_equal(annot.description, EXPECTED_DESCRIPTION)


@testing.requires_testing_data
@pytest.mark.parametrize(
    "fname,expected_channel_list",
    [
        pytest.param(
            Ref_chan_omitted_file,
            ["FP1", "FPZ", "FP2", "VEO", "EKG", "Trigger"],
            id="Ref omitted, normal order",
        ),
        pytest.param(
            Ref_chan_omitted_reordered_file,
            ["FP2", "FPZ", "FP1", "VEO", "EKG", "Trigger"],
            id="Ref omitted, reordered",
        ),
    ],
)
def test_read_files_missing_channel(fname, expected_channel_list):
    """Test reading data files that has an omitted channel."""
    # This for Git issue #8391.  In some cases, the 'labels' (.rs3 file will
    # list channels that are not actually saved in the datafile (such as the
    # 'Ref' channel).  These channels are denoted in the 'info' (.dap) file
    # in the CHAN_IN_FILE section with a '0' as their index.
    # If the CHAN_IN_FILE section is present, the code also assures that the
    # channels are sorted in the prescribed order.
    # This test makes sure the data load correctly, and that we end up with
    # the proper channel list.
    raw = read_raw_curry(fname, preload=True)
    assert raw.ch_names == expected_channel_list


@testing.requires_testing_data
@pytest.mark.parametrize(
    "fname,expected_meas_date",
    [
        pytest.param(
            Ref_chan_omitted_file,
            datetime(2018, 11, 21, 12, 53, 48, 525000, tzinfo=timezone.utc),
            id="valid start date",
        ),
        pytest.param(curry7_rfDC_file, None, id="start date year is 0"),
        pytest.param(curry7_bdf_file, None, id="start date seconds invalid"),
    ],
)
def test_meas_date(fname, expected_meas_date):
    """Test reading acquisition start datetime info info['meas_date']."""
    # This for Git issue #8398.  The 'info' (.dap) file includes acquisition
    # start date & time.  Test that this goes into raw.info['meas_date'].
    # If the information is not valid, raw.info['meas_date'] should be None
    raw = read_raw_curry(fname, preload=False)
    assert raw.info["meas_date"] == expected_meas_date


@testing.requires_testing_data
@pytest.mark.parametrize(
    "fname, others",
    [
        pytest.param(curry7_rfDC_file, (".dap", ".rs3"), id="curry7"),
        pytest.param(curry8_rfDC_file, (".cdt.dpa",), id="curry8"),
    ],
)
def test_dot_names(fname, others, tmp_path):
    """Test that dots are parsed properly (e.g., in paths)."""
    my_path = tmp_path / "dot.dot.dot"
    my_path.mkdir()
    my_path = my_path / Path(fname).parts[-1]
    fname = Path(fname)
    copyfile(fname, my_path)
    for ext in others:
        this_fname = fname.with_suffix(ext)
        to_fname = my_path.with_suffix(ext)
        copyfile(this_fname, to_fname)
    read_raw_curry(my_path)
