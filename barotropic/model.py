"""Non-divergent barotropic vorticity equation dynamical core."""
# (c) Copyright 2016 Andrew Dawson.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
from __future__ import (absolute_import, division, print_function)  #noqa

from datetime import timedelta
import math

import numpy as np

from .pyspharm_transforms import TransformsEngine


class BarotropicModel(object):
    """
    Dynamical core for a spectral non-divergent barotropic vorticity
    equation model.

    The model solves the non-divergent barotropic vorticity equation
    using a spectral method by representing the vorticity as sum of
    spherical harmonics.

    """

    def __init__(self, vrt, truncation, dt, start_time,
                 robert_coefficient=0.04, damping_coefficient=1e-4,
                 damping_order=4):
        """
        Initialize a barotropic model.

        Arguments:

        * vrt : numpy.ndarray[nlat, nlon]
            An initial vorticity field on the desired model grid. The
            grid is assumed to be Gaussian grid, and in general nlon is
            double nlat.

        * truncation : int
            The spectral truncation (triangular). A suggested value is
            nlon // 3.

        * dt : float
            The model time-step in seconds.

        * start_time : datetime.datetime
            A datetime object representing the start time of the model
            run. This doesn't affect computation, it is only used for
            metadata.

        Optional arguments:

        * robert_coefficient : default 0.04
            The coefficient for the Robert time filter.

        * damping coefficient : default 1e-4
            The coefficient for the damping term.

        * damping_order : default 4 (hyperdiffusion)
            The order of the damping.

        """
        # Model grid size:
        self.nlat, self.nlon = vrt.shape
        # Filtering properties:
        self.robert_coefficient = robert_coefficient
        # Initialize the spectral transforms engine:
        self.engine = TransformsEngine(self.nlon, self.nlat, truncation)
        # Initialize constants for spectral damping:
        m, n = self.engine.wavenumbers()
        el = (m + n) * (m + n + 1) / float(self.engine.radius) ** 2
        self.damping = damping_coefficient * \
                       (el / el[truncation]) ** damping_order
        # Initialize the grid and spectral model variables:
        self.u_grid = np.zeros([self.nlat, self.nlon], dtype=np.float64)
        self.v_grid = np.zeros([self.nlat, self.nlon], dtype=np.float64)
        self.vrt_grid = np.zeros([self.nlat, self.nlon], dtype=np.float64)
        nspec = (truncation + 1) * (truncation + 2) // 2
        self.vrt_spec = np.zeros([nspec], dtype=np.complex128)
        self.vrt_spec_prev = np.zeros([nspec], dtype=np.complex128)
        # Set the initial state:
        self.set_state(vrt)
        # Pre-compute the Coriolis parameter on the model grid:
        lats, _ = self.engine.grid_latlon()
        self.f = 2 * 7.29e-5 * np.sin(np.deg2rad(lats))[:, np.newaxis]
        # Set time control parameters:
        self.start_time = start_time
        self.t = 0
        self.dt = dt
        self.first_step = True

    @property
    def valid_time(self):
        """
        A datetime.datetime object representing the current valid time
        of the model state.

        """
        return self.start_time + timedelta(seconds=self.t)

    def set_state(self, vrt):
        """
        Set the model state from an initial vorticity.

        The vorticity must be in grid space, this method will transform
        the vorticity to spectral space using the model truncation, and
        the initial grid vorticity will be computed by converting the
        spectral vorticity back to grid space. This ensures the initial
        grid and spectral vorticity fields are equivalent.

        Argument:

        * vrt : numpy.ndarray[nlat, nlon]
            The model grid vorticity.

        """
        # Convert grid vorticity to spectral vorticity:
        self.vrt_spec[:] = self.engine.grid_to_spec(vrt)
        # Compute grid vorticity from spectral vorticity (to ensure it is
        # consistent with the spectral form):
        self.vrt_grid[:] = self.engine.spec_to_grid(self.vrt_spec)
        # Compute the wind components from the spectral vorticity, assuming
        # no divergence:
        self.u_grid[:], self.v_grid[:] = self.engine.uv_grid_from_vrtdiv_spec(
            self.vrt_spec, np.zeros_like(self.vrt_spec))
        # Set the spectral vorticity at the previous time to the current time,
        # which makes sure damping works properly:
        self.vrt_spec_prev[:] = self.vrt_spec

    def step_forward(self):
        """Step the model forward in time by one time-step."""
        if self.first_step:
            dt = self.dt
        else:
            dt = 2 * self.dt
        dudt = (self.f + self.vrt_grid) * self.v_grid
        dvdt = -(self.f + self.vrt_grid) * self.u_grid
        dzetadt, _ = self.engine.vrtdiv_spec_from_uv_grid(dudt, dvdt)
        coeffs = 1. / (1. + self.damping * self.dt)
        dzetadt = coeffs * (dzetadt - self.damping * self.vrt_spec_prev)
        if self.first_step:
            # Apply a forward-difference time integration scheme:
            new_vrt_spec = self.vrt_spec + dt * dzetadt
            self.vrt_spec[:] += (self.robert_coefficient *
                                 (new_vrt_spec - self.vrt_spec))
            # Only do the first step once:
            self.first_step = False
        else:
            # Apply a leapfrog time integration scheme:
            self.vrt_spec[:] += (self.robert_coefficient *
                                 (self.vrt_spec_prev - 2. * self.vrt_spec))
            new_vrt_spec = self.vrt_spec_prev + dt * dzetadt
            self.vrt_spec[:] += self.robert_coefficient * new_vrt_spec
        # Overwrite the t-1 time with the current time:
        self.vrt_spec_prev[:] = self.vrt_spec
        # Update the current time with the new values:
        self.vrt_spec[:] = new_vrt_spec
        self.vrt_grid[:] = self.engine.spec_to_grid(new_vrt_spec)
        self.u_grid[:], self.v_grid[:] = self.engine.uv_grid_from_vrtdiv_spec(
            new_vrt_spec, np.zeros_like(new_vrt_spec))
        # Increment the model time:
        self.t += self.dt

    def run_with_snapshots(self, run_time, snapshot_start=0,
                           snapshot_interval=None):
        """
        A generator that runs the model for a specific amount of time,
        yielding at specified intervals.

        Argument:

        * run_time : float
            The amount of time to run for in seconds.

        Keyword arguments:

        * snapshot_start : default 0
            Don't yield until at least this amount of time has passed,
            measured in seconds.

        * snapshot_interval : float
            The interval between snapshots in seconds.

        """
        snapshot_interval = snapshot_interval or self.dt
        if snapshot_interval < self.dt:
            snapshot_interval = self.dt
        target_steps = int(math.ceil((self.t + run_time) / self.dt))
        step_interval = int(math.ceil(snapshot_interval / self.dt))
        start_time = self.t
        n = 0
        while n <= target_steps:
            self.step_forward()
            n += 1
            if self.t > snapshot_start and n % step_interval == 0:
                yield self.t
