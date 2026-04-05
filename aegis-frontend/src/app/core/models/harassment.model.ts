export type HarassmentCode =
  | 'verbal_harassment'
  | 'threat'
  | 'sexual_harassment'
  | 'discrimination'
  | 'safe';

export interface HarassmentCategory {
  id: number;
  code: HarassmentCode;
  label_fr: string;
  label_ar: string;
  label_en: string;
  severity_weight: number;
}