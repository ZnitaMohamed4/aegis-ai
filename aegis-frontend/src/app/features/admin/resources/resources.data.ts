export interface IndexedDocument {
  id: string;
  name: string;
  category: string;
  language: 'fr' | 'ar' | 'en';
  chunkCount: number;
  dateAdded: Date;
  status: 'indexed' | 'processing' | 'failed';
  size: number; // in bytes
}

export interface RagMetrics {
  faithfulness: number;
  answerRelevancy: number;
  contextPrecision: number;
  totalIndexedDocs: number;
  totalChunks: number;
  lastUpdate: Date;
}

export interface UploadTask {
  id: string;
  file: File;
  progress: number;
  status:
    | 'uploading'
    | 'extracting'
    | 'chunking'
    | 'embedding'
    | 'indexing'
    | 'completed'
    | 'failed';
  language: 'fr' | 'ar' | 'en';
  category: string;
}

export const DOCUMENT_CATEGORIES = [
  { label: 'Textes légaux', value: 'legal' },
  { label: 'Guides institutionnels', value: 'guides' },
  { label: 'Procédures', value: 'procedures' },
  { label: 'Définitions internes', value: 'definitions' },
  { label: 'Autre', value: 'other' },
];

export const MOCK_INDEXED_DOCS: IndexedDocument[] = [
  {
    id: 'doc-1',
    name: 'Loi 103-13 Violences Faites aux Femmes.pdf',
    category: 'legal',
    language: 'fr',
    chunkCount: 145,
    dateAdded: new Date(Date.now() - 1000 * 60 * 60 * 24 * 5),
    status: 'indexed',
    size: 1024 * 1024 * 2.5,
  },
  {
    id: 'doc-2',
    name: 'Guide_UNICEF_Protection_Enfance.pdf',
    category: 'guides',
    language: 'fr',
    chunkCount: 320,
    dateAdded: new Date(Date.now() - 1000 * 60 * 60 * 24 * 12),
    status: 'indexed',
    size: 1024 * 1024 * 5.1,
  },
  {
    id: 'doc-3',
    name: 'DGSN_Procedure_Signalement.docx',
    category: 'procedures',
    language: 'fr',
    chunkCount: 85,
    dateAdded: new Date(Date.now() - 1000 * 60 * 60 * 24 * 2),
    status: 'indexed',
    size: 1024 * 500,
  },
  {
    id: 'doc-4',
    name: 'قانون_محاربة_العنف_ضد_النساء.pdf',
    category: 'legal',
    language: 'ar',
    chunkCount: 150,
    dateAdded: new Date(Date.now() - 1000 * 60 * 60 * 24 * 1),
    status: 'indexed',
    size: 1024 * 1024 * 1.8,
  },
  {
    id: 'doc-5',
    name: 'Harassment_Class_Definitions_v2.txt',
    category: 'definitions',
    language: 'en',
    chunkCount: 12,
    dateAdded: new Date(Date.now() - 1000 * 60 * 60 * 2),
    status: 'indexed',
    size: 1024 * 15,
  },
];

export const MOCK_RAG_METRICS: RagMetrics = {
  faithfulness: 0.88,
  answerRelevancy: 0.82,
  contextPrecision: 0.79,
  totalIndexedDocs: 24,
  totalChunks: 1458,
  lastUpdate: new Date(),
};
