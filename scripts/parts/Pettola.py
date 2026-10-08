# -*- coding: utf-8 -*-
"""Pettola (Pt): the same part as Bordino, only wider (6–14 cm and more) — a straight strip W × (edge length + Plus)
next to the panel + its copy Up up, label "Pt<w>" (cm), layer Parts::Pettola; on the panel only "Pt<w>", after
Z<n> R<w> B<w> of the edge. A panel may have both bordino and pettola. All the logic is in Bordino.py.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.modules.pop("Bordino", None)  # Rhino keeps modules from the first run for the session
import Bordino

if __name__ == "__main__":
    Bordino.main("Pettola")
