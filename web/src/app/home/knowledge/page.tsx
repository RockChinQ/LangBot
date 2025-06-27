'use client';

import CreateCardComponent from '@/app/infra/basic-component/create-card-component/CreateCardComponent';
import styles from './knowledgeBase.module.css';

export default function KnowledgePage() {
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
      </div>
    </div>
  );
}
