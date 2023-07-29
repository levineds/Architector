"""
Code for generating all valid sets of ligands mapped to a complex of given symmetry
Developed by Jan Janssen/Michael Taylor!
"""

import numpy as np
import itertools

import architector.io_obabel as io_obabel

def test_combos(combs, occupied):
    """test_combos 
    Check if a remaining combo (combos) is already occupied!

    Parameters
    ----------
    combs : np.ndarray
        Combo to check if it is already occupied.
    occupied : np.ndarray
        array of previously-occupied sites.

    Returns
    -------
    out : np.ndarrray
        remaining combos
    """
    # Compare with numpy arrays
    return combs[~np.any(np.isin(combs, occupied), axis=1)]

def flatten(S):
    """flatten 
    Flatten recursive list of lists

    Parameters
    ----------
    S : list
        arbitrarilily deep list of lists

    Returns
    -------
    out : list
        flattened list
    """
    if S == []:
        return S
    if isinstance(S[0], list):
        return flatten(S[0]) + flatten(S[1:])
    return S[:1] + flatten(S[1:])

def generate_good_combos(sel_input_lst, sel_ind, prev_lig, occupied_max):
    """generate_good_combos 
    Generate the "good" combinations of ligands mapped to the given core.
    Map list of lists to generate all sets of lists without 

    Parameters
    ----------
    sel_input_lst : list
        list of lists of possible sites for each ligand
    sel_ind : int
        the index of the current ligand
    prev_lig : list
        previously populated ligands
    occupied_max : int
        coordination number of the metal center.

    Returns
    -------
    all_lig : list
        recursive list of lists with info
    """
    if len(prev_lig) > 0 and isinstance(prev_lig[0], (list, np.ndarray)): 
        occupied = np.hstack(np.array(prev_lig, dtype=object).flatten())
    else:
        occupied = np.array(prev_lig, dtype=object).flatten()
    if len(occupied) < occupied_max:
        res = test_combos(sel_input_lst[sel_ind], occupied).tolist()
        all_lig = []
        for r in res:
            # itertools 
            prev_lig_tmp = prev_lig[:]
            prev_lig_tmp.append(r)
            lst = generate_good_combos(sel_input_lst=sel_input_lst, 
                                       sel_ind=sel_ind+1, 
                                       prev_lig=prev_lig_tmp, 
                                       occupied_max=occupied_max)
            if len(lst) > 0:
                all_lig.append(lst)
        return all_lig
    return prev_lig

def map_repeat_to_highdent(sel_con_list,nlig,denticity):
    """map_repeat_to_highdent Take in a selected connection list
    for identical ligands (repeats) and return all possible 
    locations for ligands as though they were a 
    "high denticity" single ligand.

    Parameters
    ----------
    sel_con_list : list(np.ndarray)
        selected connection indices list
    nlig : int
        number of repeated units of the ligand
    denticity : int
        denticity of repeated ligand

    Returns
    -------
    reshape_out : list(np.ndarray)
        new sel_con_list for repeat set of ligands as though a single high-denticity ligand
    refdict : dict
        dictionary of items of reshape_out and how this corresponds to original sel_con_inds.
    pseudo_dent : int
        temporary 'denticity' of ligands
    """
    all_combos = [x for x in itertools.combinations(sel_con_list,nlig)]
    highdents = np.array(all_combos)
    out = highdents.flatten()
    out = out.reshape(np.int(out.shape[0]/(nlig*denticity)),
                      nlig*denticity)
    highdents = highdents.tolist()
    reshape_out = []
    refdict = dict()
    pseudo_dent = nlig*denticity
    for i,item in enumerate(out):
        item.sort()
        _,counts = np.unique(item,return_counts=True)
        if not np.any(counts > 1):
            reshape_out.append(item.tolist())
            refdict[tuple(item)] = highdents[i]
    return reshape_out, refdict, pseudo_dent

def map_all_repeat_to_highdent(uinds, uinv, ucounts, denticities,
                               selected_con_lists):
    """map_all_repeat_to_highdent iterate over all ligand information
    and apply mapping and generate inverse mapping for different structures.

    Parameters
    ----------
    uinds : np.ndarray
        Indices of repeated ligands
    uinv : np.ndarray
        Order of repeated ligands initially input
    ucounts : np.ndarray
        Count of repeated ligands initially input
    denticities : list(int)
        denticities of the ligands originally input
    selected_con_lists : list(list)
        all possible coordination lists for input ligands

    Returns
    -------
    inv_dicts_out : dict
        structured with {index:{(a,b,c,d):[[a],[b],[c],[d]]}} for example 
        Gives mapping between a "combined" group of identical ligands,
        and what it should be with isolated ligands.
    selected_con_lists_out : list(list)
        New selected_con_lists for repeat ligands
    out_dents : list
        "Denticities" of new selected_con_lists_out
    inv_inds : list
        Information needed to invert grouped repeat ligands back to original
        ligand list.
    """
    if not np.any(ucounts > 1):
        return None, selected_con_lists, denticities, None
    else:
        selected_con_lists_intermediate = []
        pseudo_denticites = []
        inv_dicts_intermediate = []
        for i,ind in enumerate(uinds):
            if ucounts[i] == 1:
                selected_con_lists_intermediate.append(selected_con_lists[ind])
                pseudo_denticites.append(denticities[ind])
                inv_dicts_intermediate.append(None)
            else:
                reshape_out, refdict, pseudo_dent = map_repeat_to_highdent(selected_con_lists[ind],
                                                                           ucounts[i],
                                                                           denticities[ind])
                selected_con_lists_intermediate.append(reshape_out)
                pseudo_denticites.append(pseudo_dent)
                inv_dicts_intermediate.append(refdict)
        dent_order = np.argsort(pseudo_denticites)[::-1] # Sort in decreasing order
        out_dents = []
        selected_con_lists_out = []
        inv_dicts_out = dict()
        for i,j in enumerate(dent_order):
            out_dents.append(pseudo_denticites[j])
            inv_dicts_out[i] = inv_dicts_intermediate[i]
            selected_con_lists_out.append(np.array(selected_con_lists_intermediate[j]))
        inv_inds = []
        hist = dict()
        dent_order = dent_order.tolist()
        for item in uinv: # Make sure full history tracked since order will change
            if item in hist:
                hist[item] += 1
            else:
                hist[item] = 0
            inv_inds.append([item,dent_order.index(item),hist[item]])
        return inv_dicts_out, selected_con_lists_out, out_dents, inv_inds

def inv_map_highdent_to_repeat(incombo, inv_dicts, inv_inds):
    """inv_map_highdent_to_repeat take in a combination and invert it
    to original ligand list

    Parameters
    ----------
    incombo : list[np.ndarray]
        combination of ligands
    inv_dicts : dict
        structured with {index:{(a,b,c,d):[[a],[b],[c],[d]]}} for example 
        Gives mapping between a "combined" group of identical ligands,
        and what it should be with isolated ligands.
    inv_inds : list
        Information needed to invert grouped repeat ligands back to original
        ligand list.
        

    Returns
    -------
    fixed : list
        inverted ligand list to original state 
    """
    fixed = []
    for item in inv_inds:
        if isinstance(inv_dicts[item[0]],dict):
            fixed.append(inv_dicts[item[0]][tuple(incombo[item[1]])][item[2]])
        else:
            fixed.append(incombo[item[1]].tolist())
    return fixed

def select_cons(ligInputDicts, coreType, core_geo_class, params):
    """select_cons 
    Use the core geometry and ligand input dictionaries to select
    coordination atoms in line with specified molecular geometry

    Parameters
    ----------
    ligInputDicts : list
        list of ligand Input dictionaries
    coreType : str
        core geometry name
    core_geo_class: architector.io_core.Geometry
        class containing the core geometry information.
    params : dict
        parameters dictionary

    Returns
    -------
    listList : list
        list of lists of [smiles index, core index] for mapping to structures
    previously_selected : list
        previously selected indices updated with new selection.
    """
    good = False
    tmp_cn = core_geo_class.geo_cn_dict[coreType]
    geometry = core_geo_class.geometry_dict[coreType]
    geometry = np.array(geometry)
    ligLists = []
    selected_con_lists = []
    lig_charges = []
    lig_num_atoms = []
    out_liglists = []
    newLigInputDicts = ligInputDicts.copy()

    nsand = np.sum([1 for x in ligInputDicts if ((x['ligType'] == 'sandwich') or (x['ligType'] == 'haptic'))])
    if nsand > 0: # Currently sandwiches assigned to 3-denticity sites facial sites.
        n_fill_ligs = tmp_cn - np.sum([len(x['coordList']) for x in ligInputDicts if ((x['ligType'] != 'sandwich') and (x['ligType'] != 'haptic'))]) - 3*nsand
    else:
        n_fill_ligs = tmp_cn - np.sum([len(x['coordList']) for x in ligInputDicts])

    n_fill_ligs_reduced = np.floor(n_fill_ligs / len(params['fill_ligand']['coordList']))
    n_fill_secondary = n_fill_ligs - (n_fill_ligs_reduced)*len(params['fill_ligand']['coordList'])

    if n_fill_ligs < 0:
        print(n_fill_ligs, ligInputDicts)
        raise ValueError('Error - the requested complex is over-coordinated!')

    # Populate with Fill ligand and waters.
    elif n_fill_ligs > 0:
        for _ in range(int(n_fill_ligs_reduced)):
            newLigInputDicts.append(
                params['fill_ligand']
            )
        for _ in range(int(n_fill_secondary)):
            newLigInputDicts.append(
                params['secondary_fill_ligand']
            )
    # print('Ligs: ',newLigInputDicts)
    goods = []
    denticities = []
    trans = 0 # Currently just oxos!
    for k,ligInput in enumerate(newLigInputDicts):
        if (len(ligInput['coordList']) > 1) and (ligInput['ligType'] in core_geo_class.liglist_geo_map_dict.keys()):
            # print('N>1: ',k)
            if coreType in core_geo_class.liglist_geo_map_dict[ligInput['ligType']]: # Check if ligand can be mapped.
                possible_core_cons = core_geo_class.liglist_geo_map_dict[ligInput['ligType']][coreType]
                denticities.append(len(possible_core_cons[0]))
                goods.append(True)
            else:
                print(ligInput, ' cannot be mapped to :', coreType, '! - not generating!')
                goods.append(False)
                denticities.append(0)
                possible_core_cons = []
        elif (len(ligInput['coordList']) == 1): # Handle monodentates
            # print('N==1: ',k)
            if isinstance(ligInput['coordList'][0],list):
                possible_core_cons = [[ligInput['coordList'][0][1]]] # Exactly specify when exactly specified by user.
                ligInput['possible_core_cons'] = possible_core_cons
                ligInput['coordList'] = [val[0] for val in ligInput['coordList']]
                denticities.append(1)
                goods.append(True)
            elif (ligInput['smiles'] == '[O-2]') and params['force_trans_oxos']:
                if trans == 0:
                    possible_core_cons = [[0]]
                    trans += 1
                elif trans > 0:
                    possible_core_cons = [[1]]
                    trans += 1
                ligInput['possible_core_cons'] = possible_core_cons
                denticities.append(1)
                goods.append(True)
            elif 'possible_core_cons' in ligInput:
                possible_core_cons = ligInput['possible_core_cons']
                denticities.append(1)
                goods.append(True)
            else:
                possible_core_cons = [[x] for x in range(tmp_cn)]
                denticities.append(1)
                goods.append(True)
        elif (ligInput['ligType'] == 'mono') and (len(ligInput['coordList']) > 1):
            # exactly specified - flagged in io_process_input.py
            if isinstance(ligInput['coordList'][0],list):
                possible_core_cons = [[val[1] for val in ligInput['coordList']]]
                ligInput['possible_core_cons'] = possible_core_cons
                ligInput['coordList'] = [val[0] for val in ligInput['coordList']]
            else:
                possible_core_cons = ligInput['possible_core_cons']
            denticities.append(len(possible_core_cons[0]))
            goods.append(True)
        else:
            raise ValueError('{} not in known ligTypes'.format(ligInput['ligType']))
        ligobmol = io_obabel.get_obmol_smiles(ligInput['smiles']) # Get obmol for each lig 
        lig_charges.append(ligobmol.GetTotalCharge()) # Calculate total charge.
        lig_num_atoms.append(ligobmol.NumAtoms()) # Get number of atoms (estimate steric contribution)
        selected_con_lists.append(possible_core_cons)
    
    # Re-order so highest denticity ligand is always placed first.
    dent_order = np.argsort(denticities)[::-1]
    denticities = np.array(denticities)[dent_order].tolist()

    ordered_lig_charges = []
    ordered_lig_num_atoms = []
    ordered_sel_con_lists = []
    ordered_newLigInputDicts = []

    for i in dent_order:
        ordered_lig_charges.append(lig_charges[i])
        ordered_lig_num_atoms.append(lig_num_atoms[i])
        ordered_sel_con_lists.append(np.array(selected_con_lists[i])) # Convert to np array for good_combo generation!
        ordered_newLigInputDicts.append(newLigInputDicts[i])
        ordered_newLigInputDicts[-1]['ligCharge'] = lig_charges[i] # Add the ligand charges to the ligands dict
        
    lig_charges = ordered_lig_charges
    lig_num_atoms = ordered_lig_num_atoms
    newLigInputDicts = ordered_newLigInputDicts
    selected_con_lists = ordered_sel_con_lists

    ordered_newLigInputDict_strs = [str(x) for x in newLigInputDicts]

    _,uinds,uinv,ucounts = np.unique(ordered_newLigInputDict_strs,
                        return_inverse=True,
                        return_index=True,
                        return_counts=True) # Calcuate repeat ligands
    
    # Map to "higher-denticity" ligands to reduce computational overhead when recursively
    # Searching symmetries
    inv_dicts, selected_con_lists, denticities, inv_inds = map_all_repeat_to_highdent(uinds, 
                                                                                      uinv, 
                                                                                      ucounts,
                                                                                      denticities,
                                                                                      selected_con_lists)

    inverse_needed = np.any(ucounts > 1)
    # Save all selected con_lists -> test for existance of mutually exclusive sets of selected con atoms.
    # Minimize colomb energy between coordination sites, steric repulsion, and ranked order loss.
    if params['debug']:
        print('DETERMINING SYMMETRIES.')
    if all(goods):
        good_combos = generate_good_combos(sel_input_lst=selected_con_lists,
                                            sel_ind=0, prev_lig=[], occupied_max=tmp_cn)
        if params['debug']:
            print('All SYMMETRIES Enumerated - beginning energy screening.')
            if inverse_needed:
                print('Note: Treated repeat monodentate as higher denticity!')
        if len(good_combos) > 0:
            # min_score = 1e20
            out_energies = []
            out_combos = []

            tmp = flatten(good_combos) # Recursively flatten list of items 
            # Reshape into list of selected indices.
            tmp = np.array(tmp).reshape(int(len(tmp)/np.sum(denticities)),int(np.sum(denticities)))

            good_combos = tmp

            for i,combo in enumerate(good_combos[0:10000]):
                tmp_combo = []
                for j,d in enumerate(denticities): # Re-convert to list of lists matching denticities
                    tmp_combo.append(combo[int(np.sum(denticities[0:j])):int(np.sum(denticities[0:j]))+d])
                if inverse_needed: # Make sure to invert back to original ligand space for calculating "energies"
                    combo = inv_map_highdent_to_repeat(tmp_combo, inv_dicts, inv_inds)
                else:
                    combo = tmp_combo
                positions = []
                for x in combo:
                    inds = np.array(x,dtype=np.int16) # Convert to integer array
                    tmp_geos = geometry[inds]
                    posit = tmp_geos.sum(axis=0)
                    if (not np.isclose(np.linalg.norm(posit),0.0)): # Catch when posit is close to zero (e.g. tetra_planar)
                        posit = posit/np.linalg.norm(posit) # Unit vector
                    positions.append(posit)
                positions = np.array(positions)
                out_energy = 0
                #################################################################################
                ####### KEY SECTION DEFINES LIGAND RELATIVE PLACEMENT ###########################
                #################################################################################
                for inds in itertools.combinations(list(range(len(positions))),2):
                    r = np.linalg.norm(positions[inds[0]]-positions[inds[1]])
                    # Colomb energy (without constant)
                    out_energy += (lig_charges[inds[0]]*lig_charges[inds[1]]/r)*(lig_num_atoms[inds[0]]+lig_num_atoms[inds[1]])
                    # Number of atoms -> steric crowding -> multiply instead of add
                    out_energy += (lig_num_atoms[inds[0]]*lig_num_atoms[inds[1]])/r
                # # Ranked order score (omit in lieu of energy loss score for symmetry considerations)
                # out_energy += np.sum([selected_con_lists[k].index(x) for k,x in enumerate(combo)])
                out_energy = np.round(out_energy,2)
                #################################################################################
                ####### KEY SECTION DEFINES LIGAND RELATIVE PLACEMENT ###########################
                #################################################################################

                if (out_energy not in out_energies): # (out_energy < (min_score)+1e10) and
                    good = True
                    out_combos.append(combo)
                    out_energies.append(out_energy)
                    # min_score = min(out_energies)

            if good: # Only perform if a set of coord atoms is available.
                # print(out_combos,out_energies)
                sort_order = np.argsort(out_energies)[0:params['n_symmetries']] # Take n_symmetries
                for k in sort_order[0:]:
                    out_combo = out_combos[k]
                    tligLists = []
                    for j,selected_con_list in enumerate(out_combo):
                        tligList = []
                        if (newLigInputDicts[j]['ligType'] == 'sandwich') or (newLigInputDicts[j]['ligType'] == 'haptic'):
                            for i in newLigInputDicts[j]['coordList']:
                                tligList.append([i,list(selected_con_list)])
                        else:
                            for i,x in enumerate(selected_con_list):
                                tligList.append([newLigInputDicts[j]['coordList'][i],int(x)])
                        tligLists.append(tligList)
                    out_liglists.append(tligLists)
        else:
            good = False
            if params['debug']:
                print('Cannot map this ligand combination to core {} - Not generating.'.format(coreType))
    else: 
        if params['debug']:
            print('Not all individual ligands can map to this {} - Not generating!'.format(coreType))
    if params['debug']:
        print('Total valid symmetries for core {}: '.format(coreType),len(out_liglists))
    return newLigInputDicts, out_liglists, good