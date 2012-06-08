#!/usr/bin/env python
# encoding: utf-8

r""""""

from ctypes import *
import ctypes.util
from mpi4py import MPI

import os

P4EST_DIR=os.getenv('P4EST_DIR')
P4EST_HACK_SOEXT=os.getenv('P4EST_HACK_SOEXT')

#print P4EST_DIR

LIBSCPATH=ctypes.util.find_library(os.path.join(P4EST_DIR,'lib','libsc'))
LIBP4ESTPATH=ctypes.util.find_library(os.path.join(P4EST_DIR,'lib','libp4est'))

#print LIBSCPATH
#print LIBP4ESTPATH

if (P4EST_HACK_SOEXT):
    LIBSCPATH = os.path.join (P4EST_DIR, 'lib', 'libsc.so')
    LIBP4ESTPATH = os.path.join (P4EST_DIR, 'lib', 'libp4est.so')

# Wrap p4est composite structures with ctypes.  All indices are 0-based.
class sc_array (Structure):
        _fields_ = [("elem_size", c_ulonglong),
                    ("elem_count", c_ulonglong),
                    ("byte_alloc", c_longlong),
                    ("array", c_void_p)]
sc_array_pointer = POINTER (sc_array)
class mesh (Structure):
        _fields_ = [("local_num_vertices", c_int),
                    ("local_num_quadrants", c_int),
                    ("ghost_num_quadrants", c_int),
                    ("vertices", c_void_p),
                    ("quad_to_vertex", POINTER (c_int)),
                    ("ghost_to_proc", POINTER (c_int)),
                    ("ghost_to_index", POINTER (c_int)),
                    ("quad_to_quad", POINTER (c_int)),
                    ("quad_to_face", POINTER (c_byte)),
                    ("quad_to_half", sc_array_pointer)]
mesh_pointer = POINTER (mesh)
class pp (Structure):
        _fields_ = [("P4EST_DIM", c_int),       # space dimension
                    ("P4EST_HALF", c_int),      # small faces   2^(dim - 1)
                    ("P4EST_FACES", c_int),     # faces around  2 * dim
                    ("P4EST_CHILDREN", c_int),  # children      2^dim
                    ("conn", c_void_p),
                    ("p4est", c_void_p),
                    ("ghost", c_void_p),
                    ("mesh", mesh_pointer)]
pp_pointer = POINTER (pp)

def pp_get_num_leaves (pp):
        """This is just for convenience"""
        return pp.contents.mesh.contents.local_num_quadrants

# Wrap leaf iterator with ctypes
class leaf (Structure):
        _fields_ = [("pp", pp_pointer),
                    ("level", c_int),           # refinement level of leaf
                    ("which_tree", c_int),      # index of octree
                    ("which_quad", c_int),      # leaf index in this octree
                    ("total_quad", c_int),      # leaf index on this proc
                    ("tree", c_void_p),
                    ("quad", c_void_p),
                    ("lowerleft", c_double * 3),
                    ("upperright", c_double * 3)]
leaf_pointer = POINTER (leaf)

libsc = CDLL(LIBSCPATH,mode=RTLD_GLOBAL)
 
# Dynamically link in the  p4est interface
libp4est = CDLL (LIBP4ESTPATH)
libp4est.p4est_wrap_new.argtype = c_int;
libp4est.p4est_wrap_new.restype = pp_pointer;
libp4est.p4est_wrap_destroy.argtype = pp_pointer;
libp4est.p4est_wrap_leaf_first.argtype = pp_pointer;
libp4est.p4est_wrap_leaf_first.restype = leaf_pointer;
libp4est.p4est_wrap_leaf_next.argtype = leaf_pointer;
libp4est.p4est_wrap_leaf_next.restype = leaf_pointer;

class Py4estDomainTest:
    def __init__ (self):

        """
        Main idea: Below is a loop that walks through all tree leaves
        on the local processor.  For each leaf, the ctypes-wrapped p4est
        data structures can be queried to obtain neighbor information.
        Based on this information, pyclaw objects that represent the
        leaves can be created, and communication patterns can be set up
        to transfer ghost/neighbor values.

        For the encoding convention see the comment blocks in
        p4est_connectivity.h and p4est_mesh.h.  These can be used to
        create lookup tables and permutations between face neighbors.

        Currently, p4est_mesh only records face neighbors, not edges
        and corners.  This will be extended in the near future.
        """

        # Call this once per program before any other p4est function
        libp4est.p4est_wrap_init ()
       
        # Create a 2D p4est internal state on a square
        initial_level = 0
        self.pp = libp4est.p4est_wrap_new (initial_level)
        self.num_leaves = pp_get_num_leaves (self.pp)
        
        # Number of faces of a leaf (4 in 2D, 6 in 3D)
        P4EST_FACES = self.pp.contents.P4EST_FACES
        print "Py faces", P4EST_FACES, "leaves", self.num_leaves
        
        # Mesh is the lookup table for leaf neighbors
        mesh = self.pp.contents.mesh
       
        # Use the leaf iterator to loop over all leafs
        # If only a loop over leaf indices is needed,
        # do instead: for leafindex in range (0, self.num_leaves)
        leaf = libp4est.p4est_wrap_leaf_first (self.pp)
        self.patches = []
       
        # patch_counter = 0
        # Use self.num_leaves instead
        # Should be the same as the size of self.patches after this loop
        while (leaf):
                # patch_counter += 1
                # Within this loop the leaf counter is leaf.contents.total_quad
                # All indices in the p4est structures are 0-based
                
                # This is a demonstration to show off the structure
           print "Py leaf level", leaf.contents.level, \
               "tree", leaf.contents.which_tree, \
               "tree_leaf", leaf.contents.which_quad, \
               "local_leaf", leaf.contents.total_quad
           for face in range (P4EST_FACES):
               print "Py leaf face", face, "leaf", \
  mesh.contents.quad_to_quad [P4EST_FACES * leaf.contents.total_quad + face]

               #           x = pyclaw.Dimension('x', leaf.contents.lowerleft[0] , leaf.contents.upperright[0], 64)
               #           y = pyclaw.Dimension('y', leaf.contents.lowerleft[1] , leaf.contents.upperright[1], 64)

               #           patch = pyclaw.geometry.Patch ([x, y])
               #           patch.patch_index = leaf.contents.total_quad
               #           self.patches.append (patch)

           leaf = libp4est.p4est_wrap_leaf_next (leaf)
       
    def __del__ (self):
        libp4est.p4est_wrap_destroy (self.pp)    
        
        # Call this once at the end of program
        libp4est.p4est_wrap_finalize ()

ptest = Py4estDomainTest()
