import React from 'react';
import { Card, CardContent, CardHeader } from '../../../components/ui/card';

export const LoadingSkeleton: React.FC = () => (
    <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
        {[1, 2, 3].map((i) => (
            <Card key={i} className="opacity-50 animate-pulse">
                <CardHeader className="h-24 bg-surface-secondary" />
                <CardContent className="h-20" />
            </Card>
        ))}
    </div>
);
