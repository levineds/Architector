"""
Routines for performing ASE NEB from two structures generated at different distances

Developed by Michael Taylor
"""

from ase.neb import NEB
from architector.io_align_mol import neb_align
from architector.io_calc import CalcExecutor
from architector.io_molecule import convert_io_molecule

def NEB_setup(initial,final,nimages=8,neb_method='GFN2-xTB',interpolation='idpp',climb=True):
    initial_mol = convert_io_molecule(initial)
    final_mol = convert_io_molecule(final)
    final_mol_ase = neb_align(initial_mol.ase_atoms,final_mol.ase_atoms)
    final_mol.ase_atoms = final_mol_ase
    images = [initial_mol.ase_atoms]
    images += [initial_mol.ase_atoms.copy() for x in range(nimages-2)]
    images += [final_mol.ase_atoms]
    neb = NEB(images=images,climb=climb)
    neb.interpolate(method=interpolation)
    neb_images = []
    for image in neb.images:
        out = CalcExecutor(image,method=neb_method)
        neb_images.append(out.mol.ase_atoms)
    neb.images = neb_images
    return neb