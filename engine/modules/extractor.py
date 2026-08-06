#!/usr/bin/env python3
"""
Complete XER Data Extractor - Refactored for modular use in FastAPI
"""

import re
from datetime import datetime
from pathlib import Path
from collections import defaultdict
import json
from typing import Dict, List, Any, Optional

class CompleteXERExtractor:
    def __init__(self, filepath: str, file_type: str = "baseline"):
        self.filepath = Path(filepath)
        self.file_type = file_type
        self.filename = self.filepath.name
        self.raw_content = ""
        self.metadata = {}
        self.tables = {}
        self.table_relationships = defaultdict(list)
        self.extraction_stats = {}
        self.parsing_errors = []

    def extract_all(self) -> 'CompleteXERExtractor':
        self._read_raw_content()
        self._parse_header()
        self._parse_all_tables()
        self._build_relationships()
        self._calculate_statistics()
        return self

    def _read_raw_content(self):
        try:
            with open(self.filepath, 'r', encoding='windows-1252', errors='ignore') as f:
                self.raw_content = f.read()
        except Exception as e:
            self.parsing_errors.append(f"Error reading file: {str(e)}")
            raise

    def _parse_header(self):
        lines = self.raw_content.split('\n')
        if not lines:
            return
        header_line = lines[0].strip()
        parts = header_line.split('\t')
        if parts[0] == 'ERMHDR':
            self.metadata = {
                'format': 'ERMHDR',
                'version': parts[1] if len(parts) > 1 else '',
                'export_date': parts[2] if len(parts) > 2 else '',
                'database_name': parts[6] if len(parts) > 6 else '',
                'file_type': self.file_type,
                'filename': self.filename,
                'file_size_mb': round(len(self.raw_content) / (1024 * 1024), 2)
            }

    def _parse_all_tables(self):
        lines = self.raw_content.split('\n')
        current_table = None
        current_fields = []
        for line in lines[1:]:
            line = line.strip()
            if not line: continue
            parts = line.split('\t')
            try:
                if parts[0] == '%T':
                    current_table = parts[1] if len(parts) > 1 else ''
                    self.tables[current_table] = []
                elif parts[0] == '%F':
                    current_fields = parts[1:]
                elif parts[0] == '%R':
                    if current_table and current_fields:
                        row_data = {'_table_name': current_table}
                        for i, field in enumerate(current_fields):
                            value = parts[i+1] if i+1 < len(parts) else ''
                            row_data[field] = value
                        self.tables[current_table].append(row_data)
            except:
                pass

    def _build_relationships(self):
        if 'TASKPRED' in self.tables:
            for pred in self.tables['TASKPRED']:
                self.table_relationships['TASK_PREDECESSORS'].append({
                    'task_id': pred.get('task_id', ''),
                    'predecessor_task_id': pred.get('pred_task_id', ''),
                    'relationship_type': pred.get('pred_type', ''),
                    'lag_hours': pred.get('lag_hr_cnt', '0')
                })

    def _calculate_statistics(self):
        self.extraction_stats = {
            'total_tables': len(self.tables),
            'total_records': sum(len(t) for t in self.tables.values()),
            'file_type': self.file_type,
            'extraction_timestamp': datetime.now().isoformat()
        }

    def get_project_info(self) -> Dict[str, Any]:
        if 'PROJECT' not in self.tables or not self.tables['PROJECT']: return {}
        proj = self.tables['PROJECT'][0]
        return {
            'project_name': proj.get('proj_short_name', ''),
            'data_date': proj.get('last_recalc_date', '')[:10] if proj.get('last_recalc_date') else '',
            'plan_start_date': proj.get('plan_start_date', '')[:10] if proj.get('plan_start_date') else '',
            'plan_end_date': proj.get('plan_end_date', '')[:10] if proj.get('plan_end_date') else ''
        }

    def get_all_tasks(self) -> List[Dict[str, Any]]:
        return self.tables.get('TASK', [])

    def get_wbs_structure(self) -> List[Dict[str, Any]]:
        return self.tables.get('PROJWBS', [])

    def get_complete_data(self) -> Dict[str, Any]:
        return {
            'project': self.get_project_info(),
            'tasks': self.get_all_tasks(),
            'wbs': self.get_wbs_structure(),
            'tables': self.tables
        }
