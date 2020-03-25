#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Provides support for the Wavetek 39A function generator.
Rok Zitko, March 2020
"""

# IMPORTS #####################################################################


from enum import Enum

import instruments.units as u

from instruments.abstract_instruments import FunctionGenerator
from instruments.generic_scpi import SCPIInstrument
from instruments.util_fns import enum_property, unitful_property, bool_property, int_property, string_property

# CLASSES #####################################################################

def ceiling_division(n, d):
    return -(n // -d)

class Wavetek39A(SCPIInstrument, FunctionGenerator):

    """
    The Wavetek 39A is a 40MS/s function generator.

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
        Sets the arbitrary sample clock frequency.

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
        bookmark_symbol = '',
        doc="""
        Select an arbitray waveform for output.
        
        :type: `str`
        """
    )
    
    arbitrary_list_ch = string_property(
        command="ARBLISTCH",
        readonly=True,
        bookmark_symbol = '',
        doc="""
        List of all arbitrary waveforms in the channel's memory.
        
        :type: `str`
        """
    )

    arbitrary_list = string_property(
        command="ARBLIST",
        readonly=True,
        bookmark_symbol = '',
        doc="""
        List of all arbitrary waveforms in the backup memory.
        
        :type: `str`
        """
    )

    def arbitrary_delete(self, cpd):
        """
        Delete an arbitrary wavefrom from backup memory.
        
        :type: `str`
        """
        self.sendcmd("ARBDELETE {}".format(cpd))
    
    def arbitrary_clear(self, cpd):
        """
        Delete an arbitrary wavefrom from channel memory.
        
        :type: `str`
        """
        self.sendcmd("ARBCLR {}".format(cpd))
    
    def arbitrary_create(self, cpd, nrf):
        """
        Create a new black arbitrary waveform.
        
        :type cpd: `str`
        :type nrf: `int`
        """
        self.sendcmd("ARBCREATE {},{}".format(cpd,nrf))
        
    def arbitrary_get_data_csv(self, cpd):
        self.query("ARBDATACSV? {}".format(cpd))
        
    def arbitrary_define(self, cpd, csv):
        """
        Define a new or existing arbitrary waveform from a list.
        
        :type cpd: `str`
        :type csv: `iterable`
        """
        csvint = [int(x) for x in csv]
        def check_val(x): 
            if not(-2048 <= x and x <= +2047):
                raise RuntimeError("out of range {}".format(x))
        [check_val(x) for x in csvint]
        cmd = "ARBDEFCSV {},{},{}".format(cpd, str(len(csv)), ",".join([str(i) for i in csv]))
        print(cmd)
        self.sendcmd(cmd)
        
    def arbitray_edit_limits(self, nrf1, nrf2):
        self.sendcmt("ARBEDLMTS {},{}".format(nrf1,nrf2))
        
    def arbitrary_define2(self, cpd, csv):
        self.arbitrary_delete(cpd)
        self.arbitrary_create(cpd, len(csv))
        chunk_len = 10
        nr_chunk = ceiling_division(len(csv), chunk_len)
        for i in range(nr_chunk):
            self.aribitrary_edit_limits(1 + i*chunk_len, 10 + i*chunk_len)

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

    burst_count = int_property(
        command="BSTCNT",
        writeonly=True,
        doc="""
        Sets the burst count.

        :units: Number of cycles.
        :type: `int`
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

    def beep(self):
        """
        Beep once
        """
        self.sendcmd("BEEP")

    def local(self):
        """
        Returns the instrument to local operation
        """
        self.sendcmd("LOCAL")
