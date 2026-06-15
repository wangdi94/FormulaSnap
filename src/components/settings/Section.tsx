import { memo } from 'react';

export const Section = memo(function Section({
  title,
  description,
  icon,
  children,
}: {
  title: string;
  description: string;
  icon?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
      <div className="mb-4">
        <h3 className="text-base font-semibold text-gray-900 dark:text-white flex items-center gap-2">
          {icon && <span>{icon}</span>}
          {title}
        </h3>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{description}</p>
      </div>
      {children}
    </section>
  );
});
