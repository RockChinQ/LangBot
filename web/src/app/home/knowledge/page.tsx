'use client';

import CreateCardComponent from '@/app/infra/basic-component/create-card-component/CreateCardComponent';
import styles from './knowledgeBase.module.css';
import { useTranslation } from 'react-i18next';
import { useState } from 'react';
import { KnowledgeBaseVO } from '@/app/home/knowledge/components/kb-card/KBCardVO';
import KBCard from '@/app/home/knowledge/components/kb-card/KBCard';

export default function KnowledgePage() {
  const { t } = useTranslation();
  const [knowledgeBaseList, setKnowledgeBaseList] = useState<KnowledgeBaseVO[]>(
    [],
  );

  const handleKBCardClick = (kbId: string) => {
    // setIsEditForm(false);
    // setModalOpen(true);
  };

  return (
    <div>
      <div className={styles.knowledgeListContainer}>
        <CreateCardComponent
          width={'100%'}
          height={'10rem'}
          plusSize={'90px'}
          onClick={() => {
            // setIsEditForm(false);
            // setModalOpen(true);
          }}
        />

        {knowledgeBaseList.map((kb) => {
          return (
            <div key={kb.id} onClick={() => handleKBCardClick(kb.id)}>
              <KBCard kbCardVO={kb} />
            </div>
          );
        })}
      </div>
    </div>
  );
}
