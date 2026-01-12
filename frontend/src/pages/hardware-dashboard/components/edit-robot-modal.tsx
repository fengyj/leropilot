import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Modal } from '../../../components/ui/modal';
import { Button } from '../../../components/ui/button';
import { Robot } from '../../../types/hardware';

export const EditRobotModal: React.FC<{
  isOpen: boolean;
  onClose: () => void;
  robotId: string | null;
}> = ({ isOpen, onClose, robotId }) => {
  const { t } = useTranslation();
  const [robot, setRobot] = useState<Robot | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isOpen && robotId) {
      setLoading(true);
      fetch(`/api/hardware/robots/${robotId}`)
        .then(res => res.ok ? res.json() : Promise.reject(res.statusText))
        .then((data: Robot) => setRobot(data))
        .catch(() => setRobot(null))
        .finally(() => setLoading(false));
    } else if (!isOpen) {
      setRobot(null);
    }
  }, [isOpen, robotId]);

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={t('hardware.editRobotModal.title')}
      className="max-w-2xl"
    >
      <div className="p-6">
        {loading ? (
          <div className="text-sm text-content-secondary">{t('hardware.editRobotModal.loading')}</div>
        ) : robot ? (
          <div>
            <h3 className="text-lg font-bold text-content-primary mb-2">{robot.name}</h3>
            <p className="text-sm text-content-secondary">{t('hardware.editRobotModal.loadedInfo')}</p>
            {/* TODO: Implement editing form here */}
          </div>
        ) : (
          <div className="text-sm text-content-secondary">{t('hardware.editRobotModal.noData')}</div>
        )}

        <div className="mt-6 flex justify-end gap-3">
          <Button variant="secondary" onClick={onClose}>{t('common.close')}</Button>
        </div>
      </div>
    </Modal>
  );
};
