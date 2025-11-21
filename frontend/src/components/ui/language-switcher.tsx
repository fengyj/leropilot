import { Languages } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from './button';

export function LanguageSwitcher() {
  const { i18n, t } = useTranslation();

  const toggleLanguage = () => {
    const newLang = i18n.language === 'en' ? 'zh' : 'en';
    i18n.changeLanguage(newLang);
  };

  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={toggleLanguage}
      className="w-full justify-start gap-3"
      title={t('language.switchTo')}
    >
      <Languages className="h-5 w-5" />
      {i18n.language === 'en' ? t('language.chinese') : t('language.english')}
    </Button>
  );
}
