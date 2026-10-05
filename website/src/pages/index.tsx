import type {ReactNode} from 'react';
import clsx from 'clsx';
import Link from '@docusaurus/Link';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import Layout from '@theme/Layout';
import Heading from '@theme/Heading';

import styles from './index.module.css';

type Feature = {
  title: string;
  description: string;
};

const FEATURES: Feature[] = [
  {
    title: 'Scan a shelf',
    description:
      'Scan the ISBN barcode of each book with a phone. Details and covers come from Open Library.',
  },
  {
    title: 'Shelves and reading',
    description:
      'Each copy has a room, a bookcase and a shelf. Each person has a reading status, a rating and notes.',
  },
  {
    title: 'Loans and Home Keeper',
    description:
      'Lent and borrowed books get a Home Keeper task on the due date. Completing the task returns the book.',
  },
  {
    title: 'Card, entities and services',
    description:
      'Every user gets a dashboard card and a To read list. Each data action is a service, and each change fires an event.',
  },
];

function HomepageHeader() {
  const {siteConfig} = useDocusaurusContext();
  return (
    <header className={clsx('hero', styles.heroBanner)}>
      <div className="container">
        <Heading as="h1" className={styles.heroTitle}>
          {siteConfig.title}
        </Heading>
        <p className={styles.heroTagline}>{siteConfig.tagline}</p>
        <div className={styles.buttons}>
          <Link className="button button--secondary button--lg" to="/docs/intro">
            User Guide
          </Link>
          <Link
            className="button button--outline button--secondary button--lg"
            to="/developer/integrating">
            Developer Guide
          </Link>
        </div>
      </div>
    </header>
  );
}

function HomepageFeatures() {
  return (
    <section className={styles.features}>
      <div className="container">
        <div className="row">
          {FEATURES.map((feature) => (
            <div key={feature.title} className={clsx('col col--6', styles.feature)}>
              <Heading as="h3">{feature.title}</Heading>
              <p>{feature.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

export default function Home(): ReactNode {
  const {siteConfig} = useDocusaurusContext();
  return (
    <Layout title={siteConfig.title} description={siteConfig.tagline}>
      <HomepageHeader />
      <main>
        <HomepageFeatures />
      </main>
    </Layout>
  );
}
