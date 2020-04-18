#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Provides support for the Wavetek 39A function generator.
Rok Zitko, March 2020
"""

# IMPORTS #####################################################################


import struct
from enum import Enum

import instruments.units as u

from instruments.abstract_instruments import FunctionGenerator
from instruments.generic_scpi import SCPIInstrument
from instruments.util_fns import enum_property, unitful_property, bool_property, int_property, string_property

# CLASSES #####################################################################

def ceiling_division(n, d):
    return -(n // -d)

def check_arb_name(cpd):
    """
    Checks if arbitrary waveform name is valid.

    :type: `str`
    """
    if not(len(cpd) >= 1 and len(cpd) <= 8):
        raise RuntimeError("Invalid name {}".format(cpd))

def prepare_for_sending(cpd, csv):
    """
    Prepare the data for sending an arbitrary waveform to the instrument.

    :type cpd: `str`
    :type csv: `iterable`
    """
    check_arb_name(cpd)
    length = len(csv)
    if length < 4 or length > 65536:
        raise RuntimeError("incorrect length of waveform {}".format(length))
    csvint = [int(x) for x in csv]
    def check_val(x):
        if not -2048 <= x <= +2047:
            raise RuntimeError("out of range {}".format(x))
    for x in csvint:
        check_val(x)
    return length, csvint

class Wavetek39A(SCPIInstrument, FunctionGenerator):

    """
    The Wavetek 39A is a 40MS/s function generator. Arbitraty waveforms can have up to 65536 horizontal points,
    vertical range is -2048 to +2047 (12 bit), maximum peak-to-peak is 20V. Up to 100 waveforms, 256 KB NVRAM.
    Channel memory is 64 KB.

    Example usage:

    >>> import instruments as ik
    >>> import instruments.units as u
    >>> fg = ik.wavetek.Wavetek39A.open_gpib('/dev/ttyUSB0', 1)
    >>> fg.frequency = 1 * u.MHz
    >>> print(fg.offset)
    >>> fg.function = fg.Function.triangle
    """

    def __init__(self, filelike):
        super(Wavetek39A, self).__init__(filelike)
        self.terminator = ""

    # CONSTANTS #

    _UNIT_MNEMONICS = {
        FunctionGenerator.VoltageMode.peak_to_peak: "VPP",
        FunctionGenerator.VoltageMode.rms:          "VRMS",
        FunctionGenerator.VoltageMode.dBm:          "DBM",
    }

    _MNEMONIC_UNITS = dict((mnem, unit)
                           for unit, mnem in _UNIT_MNEMONICS.items())

    # FunctionGenerator CONTRACT #

    def _get_amplitude_(self):
        return (
            0.0, # amplitude is writeonly (FIXME: trigger exception instead?)
            self._MNEMONIC_UNITS["VPP"]
        )

    def _set_amplitude_(self, magnitude, units):
        self.sendcmd("AMPUNIT {}".format(self._UNIT_MNEMONICS[units]))
        self.sendcmd("AMPL {}".format(magnitude))

    # ENUMS ##

    class Function(Enum):
        """
        Enum containing valid output function modes for the Wavetek 39A
        """
        #: sinusoidal
        sinusoid = "SINE"
        #: square
        square = "SQUARE"
        #: triangular
        triangle = "TRIANG"
        #: constant voltage
        dc = "DC"
        #: positive ramp
        positive_ramp = "POSRMP"
        #: negative ramp
        negative_ramp = "NEGRMP"
        #: cosine
        cosine = "COSINE"
        #: haversine, sin^2(x/2)=(1-cos x)/2
        haversine = "HAVSIN"
        #: havercosine, (1+cos x)/2
        havercosine = "HAVCOS"
        #: sinc(x)=sin(x)/x
        sinc = "SINC"
        #: pulse
        pulse = "PULSE"
        #: pulse train
        pulse_train = "PULSTRN"
        #: arbitrary waveform
        arbitrary = "ARB"
        #: sequence of up to 16 waveforms
        sequence = "SEQ"

    class ZLoad(Enum):
        """
        Enum containing the output load settings
        """
        #: 50 Ohm termination
        Z50 = "50"
        #: 600 Ohm termination
        Z600 = "600"
        #: Z=ininity, open circuit
        OPEN = "OPEN"

    class OutputMode(Enum):
        """
        Enum containing the output mode settings
        """
        #: normal (non-inverted) output
        normal = "NORMAL"
        #: inverted output (around the same offset if offset is non-zero!)
        invert = "INVERT"

    class Mode(Enum):
        """
        Enum containing the mode settings
        """
        #: continuous operation
        cont = "CONT"
        continuous = "CONT"
        #: gated
        gate = "GATE"
        gated = "GATE"
        #: triggered burst mode (each active edge of the trigger signal produces one
        #: burst of the waveform)
        trig = "TRIG"
        triggered = "TRIG"
        #: sweep
        sweep = "SWEEP"
        #: tone mode
        tone = "TONE"

    class SweepType(Enum):
        """
        Enum containing the sweep type
        """
        #: continuous operation
        cont = "CONT"
        continuous = "CONT"
        #: triggered sweep (front TRIG IN socket, remote command, manually with MAN TRIG key)
        #: Sweep is initiated on the rising edge of the trigger signal.
        trig = "TRIG"
        triggered = "TRIG"
        #: triggered, hold and reset
        triggered_hold_reset = "THLDRST"
        #: manual sweeping (using rotary control or cursor keys)
        manual = "MANUAL"

    class SweepDirection(Enum):
        """
        Enum containing the sweep direction
        """
        #: up
        up = "UP"
        #: down
        down = "DOWN"
        #: up/down
        updn = "UPDN"
        updown = "UPDN"
        #: down/up
        dnup = "DNUP"
        downup = "DNUP"

    class SweepSpacing(Enum):
        """
        Enum containing the sweep spacing
        """
        #: linear
        lin = "LIN"
        linear = "LIN"
        #: logarithmic
        log = "LOG"
        logarithmic = "LOG"

    class SweepManual(Enum):
        """
        Enum containing the sweep manual parameters [???]
        """
        #: up
        up = "UP"
        #: down
        down = "DOWN"

    class SweepManualSpeed(Enum):
        """
        Enum containing the manual sweep step size.
        """
        #: fast
        fast = "FAST"
        #: slow
        slow = "SLOW"

    class SweepManualWrap(Enum):
        """
        Enum containing the manual sweep wrapping.
        """
        #: wrap on
        wrapon = "WRAPON"
        #: wrap off
        wrapoff = "WRAPOFF"

    class SyncOutMode(Enum):
        """
        Enum containing sync output settings
        """
        #: automatic
        auto = "AUTO"
        #: waveform sync (sync marker, for standward waveform raising edge at 0 deg point,
        #: for arbitrary waveform coincident with the first point)
        waveform_sync = "WFMSYNC"
        #: position marker for arbitrary waveform, for standard waveforms short pulse at the start of cycle
        position_marker = "POSNMKR"
        #: burst sequence done (low while the waveform is active)
        burst_done = "BSTDONE"
        #: sync signal low during the last cycle of the last waveform in a sequence, high at all other times
        sequence_sync = "SEQSYNC"
        #: positive going version of the trigger signal
        trigger = "TRIGGER"
        #: goes high at the start of the sweep, goes low at the end of the sweep
        sweep = "SWPTRG"
        #: positive edge coincident with the start of the current waveform
        phase_lock = "PHASLOC"

    class TriggerInput(Enum):
        """
        Enum containing trigger input settings
        """
        internal = "INT"
        external = "EXT"
        manual = "MAN"

    class TriggerInputEdge(Enum):
        """
        Enum containing external trigger input edge
        """
        positive = "POS"
        negative = "NEG"

    class HoldMode(Enum):
        """
        Enum containing the hold mode
        """
        #: on/off are the same as pressing the MAN HOLD key
        on = "ON"
        off = "OFF"
        #: enable/disable enable or disable the action of the MAN HOLD key
        enable = "ENAB"
        disable = "DISAB"

    class Filter(Enum):
        """
        Enum containing the output filter types
        """
        #: automatic (most appropriate for the current waveform)
        auto = "AUTO"
        #: 10MHz elliptic
        elliptic10 = "EL10"
        #: 16MHz elliptic (sine, cosine, haversine, havercosine above 10Mhz)
        elliptic16 = "EL16"
        #: 10MHz Bessel (positive and negative ramps, arbitrary and sequence)
        Bessel = "BESS"
        #: no output filtering (square wave, pulse, pulse trains)
        none = "NONE"

    class BeepMode(Enum):
        """
        Enum containing beep modes
        """
        on = "ON"
        off = "OFF"
        warnings = "WARN"
        errors = "ERROR"

    # PROPERTIES ##

    frequency = unitful_property(
        command="WAVFREQ",
        units=u.Hz,
        writeonly=True,
        doc="""
        Sets the output frequency.

        :units: As specified, or assumed to be :math:`\\text{Hz}` otherwise.
        :type: `float` or `~quantities.quantity.Quantity`
        """
    )

    period = unitful_property(
        command="WAVPER",
        units=u.s,
        writeonly=True,
        doc="""
        Sets the output period.

        :units: As specified, or assumed to be :math:`\\text{s}` otherwise.
        :type: `float` or `~quantities.quantity.Quantity`
        """
    )

    clock_frequency = unitful_property(
        command="CLKFREQ",
        units=u.Hz,
        writeonly=True,
        doc="""
        Sets the arbitrary sample clock frequency. Range 0.1Hz to 40MHz.

        :units: As specified, or assumed to be :math:`\\text{Hz}` otherwise.
        :type: `float` or `~quantities.quantity.Quantity`
        """
    )

    clock_period = unitful_property(
        command="CLKPER",
        units=u.s,
        writeonly=True,
        doc="""
        Sets the arbitrary sample clock period.

        :units: As specified, or assumed to be :math:`\\text{s}` otherwise.
        :type: `float` or `~quantities.quantity.Quantity`
        """
    )

    zload = enum_property(
        command="ZLOAD",
        enum=ZLoad,
        writeonly=True,
        doc="""
        Sets the output load.

        :type: `~Wavetek39A.ZLoad`
        """
    )

    offset = unitful_property(
        command="DCOFFS",
        units=u.volt,
        writeonly=True,
        doc="""
        Sets the offset voltage for the output waveform.

        :units: As specified, or assumed to be :math:`\\text{V}` otherwise.
        :type: `float` or `~quantities.quantity.Quantity`
        """
    )

    function = enum_property(
        command="WAVE",
        enum=Function,
        writeonly=True,
        doc="""
        Sets the output function of the function generator.

        :type: `~Wavetek39A.Function`
        """
    )

    pulse_period = unitful_property(
        command="PULSPER",
        units=u.s,
        writeonly=True,
        doc="""
        Sets the pulse period.

        :units: As specified, or assumed to be :math:`\\text{s}` otherwise.
        :type: `float` or `~quantities.quantity.Quantity`
        """
    )

    pulse_width = unitful_property(
        command="PULSWID",
        units=u.s,
        writeonly=True,
        doc="""
        Sets the pulse width.

        :units: As specified, or assumed to be :math:`\\text{s}` otherwise.
        :type: `float` or `~quantities.quantity.Quantity`
        """
    )

    pulse_delay = unitful_property(
        command="PULSDLY",
        units=u.s,
        writeonly=True,
        doc="""
        Sets the pulse delay.

        :units: As specified, or assumed to be :math:`\\text{s}` otherwise.
        :type: `float` or `~quantities.quantity.Quantity`
        """
    )

    pulse_train_length = int_property(
        command="PULSTRNLEN",
        writeonly=True,
        doc="""
        Sets the number of pulses in the pulse-train.

        :units: Number.
        :type: `int`
        """
    )

    pulse_train_period = unitful_property(
        command="PULSTRNPER",
        units=u.s,
        writeonly=True,
        doc="""
        Sets the pulse-train period.

        :units: As specified, or assumed to be :math:`\\text{s}` otherwise.
        :type: `float` or `~quantities.quantity.Quantity`
        """
    )

    pulse_train_base_line = unitful_property(
        command="PULSTRNBASE",
        units=u.V,
        writeonly=True,
        doc="""
        Sets the pulse-train base line voltage.

        :units: As specified, or assumed to be :math:`\\text{V}` otherwise.
        :type: `float` or `~quantities.quantity.Quantity`
        """
    )

    # pulse_train_level = unitful_property(  ## has two parameters!

    arbitrary = string_property(
        command="ARB",
        writeonly=True,
        bookmark_symbol='',
        doc="""
        Select an arbitray waveform for output.

        :type: `str`
        """
    )

    arbitrary_list_ch = string_property(
        command="ARBLISTCH",
        readonly=True,
        bookmark_symbol='',
        doc="""
        List of all arbitrary waveforms in the channel's memory.

        :type: `str`
        """
    )

    arbitrary_list = string_property(
        command="ARBLIST",
        readonly=True,
        bookmark_symbol='',
        doc="""
        List of all arbitrary waveforms in the backup memory.

        :type: `str`
        """
    )

    def arbitrary_delete(self, cpd):
        """
        Delete an arbitrary wavefrom from backup memory.
        A waveform used by a non-active sequence can be deleted but the sequence will not subsequently
        run properly and should be modified to exclude the deleted waveform.

        :type: `str`
        """
        check_arb_name(cpd)
        self.sendcmd("ARBDELETE {}".format(cpd))

    def arbitrary_clear(self, cpd):
        """
        Delete an arbitrary wavefrom from channel memory.
        A waveform cannot be deleted from a channel’s memory if it is running on that channel.
        If an arb waveform sequence is running no waveforms can be deleted from that channel,
        whether they are used in the sequence or not.
        Waveforms must be deleted from the channel’s memory before they can be deleted from the back-up memory.
        (i.e. call arbitrary_clear before arbitrary_delete)

        :type: `str`
        """
        check_arb_name(cpd)
        self.sendcmd("ARBCLR {}".format(cpd))

    def arbitrary_create(self, cpd, nrf):
        """
        Create a new blank arbitrary waveform.

        :type cpd: `str`
        :type nrf: `int`
        """
        check_arb_name(cpd)
        self.sendcmd("ARBCREATE {},{}".format(cpd, nrf))

    def _arbitrary_send_data_csv(self, cpd, csv, command):
        length, csvint = prepare_for_sending(cpd, csv)
        cmd = "{} {},{},{}".format(command, cpd, str(length), ",".join([str(i) for i in csvint]))
        self.sendcmd(cmd)

    def _arbitrary_send_data(self, cpd, csv, command):
        length, csvint = prepare_for_sending(cpd, csv)
        bin_data = struct.pack('>{}h'.format(length), *csvint)
        size_str = str(len(bin_data))
        len_size_str = len(size_str)
        header = '#{}{}'.format(len_size_str, size_str)
        cmd = "{} {},{},{}{}".format(command, cpd, str(length), header, bin_data)
        self.sendcmd(cmd)

    def arbitrary_define_csv(self, cpd, csv):
        """
        Define a new or existing arbitrary waveform from a list.

        :type cpd: `str`
        :type csv: `iterable`
        """
        self._arbitrary_send_data_csv(cpd, csv, "ARBDEFCSV")

    def arbitrary_define(self, cpd, csv):
        """
        Define a new or existing arbitrary waveform from a list.

        :type cpd: `str`
        :type csv: `iterable`
        """
        self._arbitrary_send_data(cpd, csv, "ARBDEF")

    def arbitrary_get_data_csv(self, cpd):
        """
        Returns the arbitrary waveform data as ASCII data.

        :rtype: `str`
        """
        check_arb_name(cpd)
        self.query("ARBDATACSV? {}".format(cpd))

    def arbitray_edit_limits(self, nrf1, nrf2):
        """
        Define editing limits for the currently edited arbitrary waveform.

        :type nrf1: `int`
        :type nrf2: `int`
        """
        self.sendcmd("ARBEDLMTS {},{}".format(nrf1, nrf2))

    def arbitrary_data_csv(self, cpd, csv):
        self._arbitrary_send_data_csv(cpd, csv, "ARBDATACSV")

    def arbitrary_data(self, cpd, csv):
        self._arbitrary_send_data(cpd, csv, "ARBDATA")

    phase = unitful_property(
        command="PHASE",
        units=u.degree,
        writeonly=True,
        doc="""
        Sets the phase for the output waveform.

        :units: As specified, or assumed to be degrees (:math:`{}^{\\circ}`)
            otherwise.
        :type: `float` or `~quantities.quantity.Quantity`
        """
    )

    sweep_start_frequency = unitful_property(
        command="SWPSTARTFRQ",
        units=u.Hz,
        writeonly=True,
        doc="""
        Sets the sweep start frequency. Minimum is 1 mHz.

        :units: As specified, or assumed to be Hz otherwise.
        :type: `float` or `~quantities.quantity.Quantity`   
        """
    )

    sweep_stop_frequency = unitful_property(
        command="SWPSTOPFRQ",
        units=u.Hz,
        writeonly=True,
        doc="""
        Sets the sweep stop frequency. Maximum is 16 MHz for all waveforms,
        including triangle, ramp and square wave.

        :units: As specified, or assumed to be Hz otherwise.
        :type: `float` or `~quantities.quantity.Quantity`   
        """
    )

    sweep_centre_frequency = unitful_property(
        command="SWPCENTFRQ",
        units=u.Hz,
        writeonly=True,
        doc="""
        Sets the sweep centre frequency.

        :units: As specified, or assumed to be Hz otherwise.
        :type: `float` or `~quantities.quantity.Quantity`   
        """
    )

    sweep_span = unitful_property(
        command="SWPSPAN",
        units=u.Hz,
        writeonly=True,
        doc="""
        Sets the sweep frequency span.

        :units: As specified, or assumed to be Hz otherwise.
        :type: `float` or `~quantities.quantity.Quantity`   
        """
    )

    sweep_time = unitful_property(
        command="SWPTIME",
        units=u.s,
        writeonly=True,
        doc="""
        Sets the sweep time. 0.03s to 999s with 3-digit resolution.

        :units: As specified, or assumed to be s otherwise.
        :type: `float` or `~quantities.quantity.Quantity`   
        """
    )

    sweep_type = enum_property(
        command="SWPTYPE",
        enum=SweepType,
        writeonly=True,
        doc="""
        Sets the sweep type.

        :type: `~Wavetek39A.SweepType`
        """
    )

    sweep_direction = enum_property(
        command="SWPDIRN",
        enum=SweepDirection,
        writeonly=True,
        doc="""
        Sets the sweep direction.

        :type: `~Wavetek39A.SweepDirection`
        """
    )

    sweep_sync = bool_property(
        "SWPSYNC",
        inst_true="ON",
        inst_false="OFF",
        writeonly=True,
        doc="""
        Sets the sweep syncs on and off. If on (default), the generator steps from the stop
        frequency to zero frequency and then starts the next sweep from the first point of the
        waveform, synchronized to the internally generated trigger signal.
        """
    )

    sweep_spacing = enum_property(
        command="SWPSPACING",
        enum=SweepSpacing,
        writeonly=True,
        doc="""
        Sets the sweep spacing.

        :type: `~Wavetek39A.SweepSpacing`
        """
    )

    sweep_marker = unitful_property(
        command="SWPMARKER",
        units=u.Hz,
        writeonly=True,
        doc="""
        Sets the sweep marker (rear panel CURSOR/MARKER OUT socket).

        :units: As specified, or assumed to be Hz otherwise.
        :type: `float` or `~quantities.quantity.Quantity`
        """
    )

    sweep_manual_speed = enum_property(
        command="SWPMANUAL",
        enum=SweepManualSpeed,
        writeonly=True,
        doc="""
        Sets the manual step size.

        :type: `~Wavetek39A.SweepManualSpeed`
        """
    )

    sweep_manual_wrap = bool_property(
        "SWPMANUAL",
        inst_true="WRAPON",
        inst_false="WRAPOFF",
        writeonly=True,
        doc="""
        Sets the sweep wrapping on/off.
        """
    )

    output = bool_property(
        "OUTPUT",
        inst_true="ON",
        inst_false="OFF",
        writeonly=True,
        doc="""
        Sets the output on and off.
        """
    )

    output_mode = enum_property(
        command="OUTPUT",
        enum=OutputMode,
        writeonly=True,
        doc="""
        Sets the output mode (normal vs. inverted).

        :type: `~Wavetek39A.OutputMode`
        """
    )

    mode = enum_property(
        command="MODE",
        enum=Mode,
        writeonly=True,
        doc="""
        Sets the mode.

        :type: `~Wavetek39A.Mode`
        """
    )

    syncout = bool_property(
        "SYNCOUT",
        inst_true="ON",
        inst_false="OFF",
        writeonly=True,
        doc="""
        Sets the sync output on and off.
        """
    )

    syncout_mode = enum_property(
        command="SYNCOUT",
        enum=SyncOutMode,
        writeonly=True,
        doc="""
        Sets the sync output mode.

        :type: `~Wavetek39A.SyncOut`
        """
    )

    trigger_input = enum_property(
        command="TRIGIN",
        enum=TriggerInput,
        writeonly=True,
        doc="""
        Sets the trigger input.

        :type: `~Wavetek39A.TriggerInput`
        """
    )

    trigger_input_edge = enum_property(
        command="TRIGIN",
        enum=TriggerInputEdge,
        writeonly=True,
        doc="""
        Sets the edge for external trigger input.

        :type: `~Wavetek39A.TriggerInputEdge`
        """
    )

    trigger_period = unitful_property(
        command="TRIGPER",
        units=u.s,
        writeonly=True,
        doc="""
        Sets the internal trigger period.

        :units: As specified, or assumed to be seconds otherwise.
        :type: `float` or `~quantities.quantity.Quantity`
        """
    )

    def reset(self):
        """
        Resets the instrument parameters to their default values.
        """
        self.sendcmd("*RST")

    def force_trigger(self):
        """
        Force a trigger
        """
        self.sendcmd("FORCETRG")

    burst_count = int_property(
        command="BSTCNT",
        writeonly=True,
        doc="""
        Sets the burst count.

        :units: Number of cycles.
        :type: `int`
        """
    )

    def recall(self, nrf):
        """
        Recall the set up in store 'nrf'. 0-9. 0 are default settings.
        """
        if not 0 <= nrf <= 9:
            raise RuntimeError("out of range {}".format(nrf))
        self.sendcmd("*RCL {}".format(nrf))

    def save(self, nrf):
        """
        Save the set up in store 'nrf'. 1-9.
        """
        if not 1 <= nrf <= 9:
            raise RuntimeError("out of range {}".format(nrf))
        self.sendcmd("*SAV {}".format(nrf))

    def manual_trigger(self):
        """
        Same as pressing the MAN TRIG key.
        """
        self.sendcmd("*TRG")

    holdmode = enum_property(
        command="HOLD",
        enum=HoldMode,
        writeonly=True,
        doc="""
        Sets the hold mode.

        :type: `~Wavetek39A.HoldMode`
        """
    )

    filter = enum_property(
        command="FILTER",
        enum=Filter,
        writeonly=True,
        doc="""
        Sets the output filter type.

        :type: `~Wavetek39A.Filter`
        """
    )

    beepmode = enum_property(
        command="BEEPMODE",
        enum=BeepMode,
        writeonly=True,
        doc="""
        Sets the beep mode.

        :type: `~Wavetek39A.BeepMode`
        """
    )

    def beep(self):
        """
        Beep once
        """
        self.sendcmd("BEEP")

    def local(self):
        """
        Returns the instrument to local operation and unlock the keyboard.
        """
        self.sendcmd("LOCAL")
