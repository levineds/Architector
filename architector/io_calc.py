"""
Namely the class to handle ase calculations or obmol calculations of metal complexes.

Developed by Michael Taylor
"""


import numpy as np
import time
import copy
import os
# import architector.io_xtb_calc as io_xtb_calc
import architector.io_obabel as io_obabel
from architector.io_align_mol import rmsd_align
import architector.arch_context_manage as arch_context_manage
import architector.io_molecule as io_molecule
import architector.io_ptable as io_ptable
from ase.io import Trajectory
from ase.optimize import LBFGSLineSearch
from ase.constraints import (FixAtoms, FixBondLengths)

### Add any other ASE calculator here.
# To extend to other methods.
from xtb.ase.calculator import XTB
# from tblite.ase import TBLite -> No GFN-FF support yet

params={
"save_trajectories": False, # Only on XTB methods
"dump_ase_atoms": False,
"ase_atoms_db_name": 
    'architector_ase_db.json',
"temp_prefix":"/tmp/",
"ase_db_tmp_name":"/tmp/architector_ase_db.json",
# Cutoff parameters
"assemble_sanity_checks":True, # Turn on/off assembly sanity checks.
"assemble_graph_sanity_cutoff":1.8,
# Graph Sanity cutoff for imposed molecular graph represents the maximum elongation of bonds
# rcov1*full_graph_sanity_cutoff is the maximum value for the bond lengths.
"assemble_smallest_dist_cutoff":0.3,
# Smallest dist cutoff screens if any bonds are less than smallest_dist_cutoff*sum of cov radii
# Will not be evaluated by XTB if they are lower.
"assemble_min_dist_cutoff":4,
# Smallest min dist cutoff screens if any atoms are at minimum min_dist_cutoff*sum of cov radii
# away from ANY other atom (indicating blown-up structure) 
# - will not be evaluated by XTB if they are lower.
"full_sanity_checks":True, # Turn on/off final sanity checks.
"full_graph_sanity_cutoff":1.7,
# full_graph_sanity_cutoff can be tightened to weed out distorted geometries (e.g. 1.5 for non-group1-metals) 
"full_smallest_dist_cutoff":0.55,
"full_min_dist_cutoff":3.5,
# Electronic parameters
"metal_ox": None, # Oxidation State
"metal_spin": None, # Spin State
"xtb_solvent": 'none', # Add any named XTB solvent!
"calculator_kwargs":dict(), # ASE calculator kwargs.
"ase_opt_kwargs":dict(), # ASE optimizer kwargs.
"xtb_accuracy":1.0, # Numerical Accuracy for XTB calculations
"xtb_electronic_temperature":300, # In K -> fermi smearing - increase for convergence on harder systems
"xtb_max_iterations":250, # Max iterations for xtb SCF.
"full_spin": None, # Assign spin to the full complex (overrides metal_spin)
"full_charge": None, # Assign charge to the complex (overrides ligand charges and metal_ox)!
"full_method":"GFN2-xTB", # Which xtb method to use for final cleaning/evaulating conformers.
"assemble_method":"GFN2-xTB",
"ff_preopt":False,
"override_oxo_opt":False,
"fmax":0.1,
"maxsteps":1000,
"vdwrad_metal":None,
"covrad_metal":None,
"scaled_radii_factor":None,
"force_generation":False,
"species_run":False,
"debug":False,
}

class CalcExecutor:
    def __init__(self, structure, parameters={}, init_sanity_check=False,
                final_sanity_check=False, relax=False, assembly=False,
                method='GFN2-xTB', xtb_solvent='none', xtb_accuracy=1.0,
                xtb_electronic_temperature=300, xtb_max_iterations=250,
                fmax=0.1, maxsteps=1000, ff_preopt_run=False,
                detect_spin_charge=False, fix_m_neighbors=False,
                default_params=params, ase_opt_method=None, species_run=False,
                intermediate=False,skip_spin_assign=False,
                calculator=None, debug=False):
        """CalcExecutor is the class handling all calculations of full metal-ligand complexes.

        Parameters
        ----------
        structure : architector.io_molecule.Molecule
            Structure to evaluate.
        parameters : dict, optional
            parameters passed, by default None
        init_sanity_check : bool, optional
            perform initial sanity checks before proceeding, by default False
        final_sanity_check : bool, optional
            perform final sanity checks, by default False
        relax : bool, optional
            relax the complex, by default False
        assembly : bool, optional
            if this is an assembly calculation or not; if assembly will
            perform only single point and set to assembly cutoffs, by default False
        method : str, optional
            Level of theory to perform calculation at, by default 'GFN2-xTB'
            Current Valid options -> 'GFN2-xTB', 'UFF', 'GFN-FF', 'MMFF'
            Adding new methods will require integration with their ase calculators.
        xtb_solvent : str, optional
            Solvent passed to xTB calculator, by default 'none'
        xtb_accuracy : float, optional
            Accuracy for xtb SCF convergence, default 1.0 
        xtb_electronic_temperature : float, optional
            Electronic temp for smearing, default 300 K
        xtb_max_iterations : float, optional
            Maximum iterations for xtb SCF convergence, default 250.
        fmax : float, optional
            Max force in eV/Angstrom, by default 0.1
        maxsteps : int, optional
            Total number of optimization steps to take, by default 1000
        ff_preopt_run : bool, optional
            Perform forcefield pre-optimization?, by default False
        detect_spin_charge : bool, optional
            Detect the charge and spin with openbabel routines?, by default False
        fix_m_neighbors : bool, optional
            Set the metal neighbors as fixed, by default False
        default_params :dict, optional
            default parameters to evaluate to, by default params
        ase_opt_method : ase.optimize Optimizer, optional
            Valid ase style optimizer if desired, by default None
        species_run : bool, optional
            Flag if this run is performed for a "species" to be added.
        intermediate : bool, optional
            If this is an "intermediate" calculation or not, by default False
        skip_spin_assign : bool, optional
            Skip the re-assignment of spin to a molcule during the calculation, by default False
        calculator : ase.calculators Calculator, optional
            Valid ase style calculator if desired, by default None
        debug : bool, optional 
            Whether to debug print or not, defualt False
        """

        self.in_struct = structure
        self.mol = io_molecule.convert_io_molecule(structure)
        self.method = method
        default_params = params.copy()
        default_params['debug'] = debug
        default_params.update(parameters)
        self.parameters = default_params
        self.init_sanity_check = init_sanity_check
        self.final_sanity_check = final_sanity_check
        self.calculator = calculator
        self.relax = relax
        self.ase_opt_method = ase_opt_method
        self.assembly = assembly
        self.ff_preopt_run = ff_preopt_run
        self.xtb_solvent = xtb_solvent
        self.xtb_accuracy = xtb_accuracy
        self.xtb_electronic_temperature = xtb_electronic_temperature
        self.xtb_max_iterations = xtb_max_iterations
        self.fmax = fmax
        self.fix_m_neighbors = fix_m_neighbors
        self.maxsteps = maxsteps
        self.species_run = species_run
        self.skip_spin_assign = skip_spin_assign
        self.force_generation = False
        self.force_oxo_relax = False
        
        self.detect_spin_charge = detect_spin_charge
        if len(parameters) > 0:
            for key,val in parameters.items():
                setattr(self,key,val)

        if assembly:
            self.init_sanity_check = True
            self.relax = False
            self.method = self.assemble_method
        elif species_run:
            if isinstance(intermediate,str):
                if intermediate == 'rotation':
                    self.method = self.species_intermediate_method
                    self.relax = False
                elif intermediate == 'main':
                    self.method = self.species_method
                    self.relax = self.species_intermediate_relax
                    self.force_oxo_relax = True
            else:
                self.method = self.species_method
                self.relax = self.species_relax
        elif len(parameters) > 0:
            if self.ff_preopt_run:
                self.method = 'UFF'
                self.relax=True
            else:
                self.method = self.full_method
        else:
            if self.ff_preopt_run:
                self.method = 'UFF'
                self.relax=True

        if self.ase_opt_method is None: # Default to LBFGSLineSearch
            self.opt_method = LBFGSLineSearch
        else:
            self.opt_method = self.ase_opt_method
        # Temporary logfile or not for ase optimizer
        if self.parameters['debug']: # Set logfile to suppress stdout output.
            self.logfile = None
        else:
            self.logfile = 'tmp.log'

        # Output properties
        self.energy = None
        self.init_energy = None
        self.errors = []
        self.successful = False
        self.trajectory = None
        self.rmsd = None
        self.calc_time = time.time()
        self.done = False
        self.calculate()

    def calculate(self):
        if self.init_sanity_check and self.parameters.get('assemble_sanity_checks',True):
            self.mol.dist_sanity_checks(params=self.parameters,assembly=self.assembly)
            self.mol.graph_sanity_checks(params=self.parameters,assembly=self.assembly)
        if self.mol.dists_sane:
            if (not self.species_run) and (not self.skip_spin_assign):
                self.mol.calc_suggested_spin(params=self.parameters)
            obabel_ff_requested = False
            if (self.calculator is not None) and ('custom' in self.method): # If ASE calculator passed use that by default
                calc = self.calculator(**self.calculator_kwargs)
                # Here, if a calculator needs spin/charge information in another way we can assign.
                # Or handle as a different use case.
                uhf_vect = np.zeros(len(self.mol.ase_atoms))
                uhf_vect[0] = self.mol.uhf
                charge_vect = np.zeros(len(self.mol.ase_atoms))
                charge_vect[0] = self.mol.charge
                self.mol.ase_atoms.set_initial_charges(charge_vect)
                self.mol.ase_atoms.set_initial_magnetic_moments(uhf_vect)
                ##### TODO ######
                # This is currently a bit hack-y. Need better workaround for handling actinide potentials.
                self.mol.actinides = [i for i,x in enumerate(self.mol.ase_atoms.get_chemical_symbols()) if (x in io_ptable.lanthanides)]
                self.mol.actinides_swapped = True
                self.mol.swap_actinide()
                ##### TODO ######
            elif 'gfn' in self.method.lower():
                calc = XTB(method=self.method, solvent=self.xtb_solvent,
                           max_iterations=self.xtb_max_iterations,
                           electronic_temperature=self.xtb_electronic_temperature,
                           accuracy=self.xtb_accuracy)
                        #    verbosity=0)
                # Difference of more than 1. Still perform a ff_preoptimization if requested.
                if (np.abs(self.mol.xtb_charge - self.mol.charge) > 1):
                    if ((not self.override_oxo_opt) or (self.assembly)) and (not self.force_oxo_relax):
                        self.relax = False # E.g - don't relax if way off in oxdiation states (III) vs (V or VI)
                    elif self.assembly: # FF more stable for highly charged assembly complexes.
                        self.method = 'GFN-FF'
                uhf_vect = np.zeros(len(self.mol.ase_atoms))
                if self.method != 'GFN-FF':
                    uhf_vect[0] = self.mol.xtb_uhf
                charge_vect = np.zeros(len(self.mol.ase_atoms))
                if self.method != 'GFN-FF':
                    charge_vect[0] = self.mol.xtb_charge
                self.mol.ase_atoms.set_initial_charges(charge_vect)
                self.mol.ase_atoms.set_initial_magnetic_moments(uhf_vect)
            elif ('uff' in self.method.lower()) or ('mmff' in self.method.lower()):
                obabel_ff_requested = True
            else:
                raise ValueError('Warning - no known method or calculator requested.')
            if not obabel_ff_requested:
                self.mol.ase_atoms.calc = calc
                if self.relax:
                    if self.parameters.get("freeze_molecule_add_species",False) and ('custom' not in self.method):
                        if self.parameters['debug']:
                            print('Fixing first component!')
                        fix_inds = self.mol.find_component_indices(component=0)
                        c = FixAtoms(indices=fix_inds.tolist())
                        self.mol.ase_atoms.set_constraint(c)
                    with arch_context_manage.make_temp_directory(
                        prefix=self.parameters['temp_prefix']) as _:
                        try:
                            self.init_energy = copy.deepcopy(self.mol.ase_atoms.get_total_energy())
                            if self.parameters['save_trajectories']:
                                if self.logfile is not None:
                                    dyn = self.opt_method(self.mol.ase_atoms, 
                                                        trajectory='temp.traj',
                                                        logfile=self.logfile,
                                                        **self.ase_opt_kwargs)
                                else:
                                    dyn = self.opt_method(self.mol.ase_atoms, 
                                                        trajectory='temp.traj',
                                                        **self.ase_opt_kwargs)
                            else:
                                if self.logfile is not None:
                                    dyn = self.opt_method(self.mol.ase_atoms,
                                                        logfile=self.logfile,
                                                        **self.ase_opt_kwargs)
                                else:
                                    dyn = self.opt_method(self.mol.ase_atoms,
                                                          **self.ase_opt_kwargs)
                            dyn.run(fmax=self.fmax,steps=self.maxsteps)
                            if self.parameters['save_trajectories']:
                                self.read_traj()
                            self.energy = self.mol.ase_atoms.get_total_energy()
                            self.rmsd, _, _ = rmsd_align(self.mol.ase_atoms,
                                                    io_molecule.convert_io_molecule(self.in_struct).ase_atoms,
                                                    in_place=True)
                            self.calc_time = time.time() - self.calc_time
                            self.successful = True
                        except Exception as e:
                            self.errors.append(e)
                            if self.parameters['debug']:
                                print('Warning - method did not converge!',e)
                                print('Mol XTB Charge {} Spin {}\n'.format(self.mol.xtb_charge,self.mol.xtb_uhf))
                                print('Mol ase Charge {} Spin {}\n'.format(self.mol.ase_atoms.get_initial_charges().sum(),
                                                                           self.mol.ase_atoms.get_initial_magnetic_moments().sum()))
                            self.energy = 10000
                            self.init_energy = 10000
                            self.calc_time = time.time() - self.calc_time
                    # Remove constraint
                    if self.parameters.get("freeze_molecule_add_species",False):
                        if self.parameters['debug']:
                            print('Removing fixing first component!')
                        self.mol.ase_atoms.set_constraint() 
                else:
                    with arch_context_manage.make_temp_directory(
                        prefix=self.parameters['temp_prefix']) as _:
                        try:
                            self.energy = self.mol.ase_atoms.get_total_energy()
                            self.init_energy = copy.deepcopy(self.energy)
                            self.successful = True
                        except Exception as e:
                            self.errors.append(e)
                            if self.parameters['debug']:
                                print('Warning - method did not converge!',e)
                                print('Mol XTB Charge {} Spin {}\n'.format(self.mol.xtb_charge,self.mol.xtb_uhf))
                                print('Mol ase Charge {} Spin {}\n'.format(self.mol.ase_atoms.get_initial_charges().sum(),
                                            self.mol.ase_atoms.get_initial_magnetic_moments().sum()))
                            self.energy = 10000
                            self.init_energy = 10000
                            self.calc_time = time.time() - self.calc_time
            else: 
                if self.relax:
                    try:
                        self.init_energy = io_obabel.obmol_energy(self.mol)
                        out_atoms, energy = io_obabel.obmol_opt(self.mol, center_metal=True, 
                                fix_m_neighbors=self.fix_m_neighbors, # Note - fixing metal neighbors in UFF
                                    # Done to maintain metal center symmetry
                                    return_energy=True)
                        self.successful = True
                        self.energy = energy
                        self.mol.ase_atoms.set_positions(out_atoms.get_positions())
                        self.rmsd, _, _ = rmsd_align(self.mol.ase_atoms,
                                                    io_molecule.convert_io_molecule(self.in_struct).ase_atoms,
                                                    in_place=True)
                    except Exception as e:
                        self.errors.append(e)
                        if self.parameters['debug']:
                            print('Warning - method did not converge!',e)
                else:
                    try:
                        self.energy = io_obabel.obmol_energy(self.mol)
                        self.init_energy = copy.deepcopy(self.energy)
                        self.successful = True
                    except Exception as e:
                        self.errors.append(e)
                        if self.parameters['debug']:
                            print('Warning - method did not converge!',e)
            if (not self.successful) and (self.force_generation):
                try:
                    self.energy = io_obabel.obmol_energy(self.mol)
                    self.init_energy = copy.deepcopy(self.energy)
                    self.successful = True
                except Exception as e:
                    self.errors.append(e)
                    if self.parameters['debug']:
                        print('Warning - method did not converge!',e)
            self.calc_time = time.time() - self.calc_time
            self.done = True
        else:
            self.errors.append('Min dist checks failed. Not evaluated')
        # Check after done
        self.mol.swap_actinide()
        if self.final_sanity_check:
            self.mol.dist_sanity_checks(params=self.parameters,assembly=self.assembly)
            self.mol.graph_sanity_checks(params=self.parameters,assembly=self.assembly)

        # Reset structure to inital state to avoid nans in output structures.
        if np.any(np.isnan(self.mol.ase_atoms.get_positions())):
            self.mol = io_molecule.convert_io_molecule(self.in_struct)
            self.mol.calc_suggested_spin(params=self.parameters)
        
        if self.parameters['save_trajectories'] and (self.trajectory is not None):
            self.dump_traj()
        elif self.parameters['save_trajectories']:
            pass
        elif self.parameters['dump_ase_atoms'] and (self.mol.ase_atoms.calc is not None) and \
            (not self.assembly):
            self.parameters['ase_db'].write(self.mol.ase_atoms,relaxed=self.relax)
            

    def read_traj(self):
        pwd = os.path.abspath('.')
        traj = Trajectory(os.path.join(pwd,'temp.traj'))
        self.trajectory = traj

    def dump_traj(self):
        for i,ats in enumerate(self.trajectory):
            end = i
        for i,ats in enumerate(self.trajectory):
            if i < end:
                self.parameters['ase_db'].write(ats,geo_step=i,relaxed=False)
            else:
                self.parameters['ase_db'].write(ats,geo_step=i,relaxed=True)


