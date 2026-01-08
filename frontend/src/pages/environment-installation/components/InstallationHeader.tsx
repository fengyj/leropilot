

interface InstallationHeaderProps {
    pageTitle: string;
    pageSubtitle: string;
}

export const InstallationHeader = ({ pageTitle, pageSubtitle }: InstallationHeaderProps) => {
    return (
        <div className="space-y-2">
            <h1 className="text-content-primary text-2xl font-bold">
                {pageTitle}
            </h1>
            <p className="text-content-secondary">
                {pageSubtitle}
            </p>
        </div>
    );
};
