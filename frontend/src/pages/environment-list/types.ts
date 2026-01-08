export interface Environment {
    id: string;
    display_name: string;
    ref: string;
    python_version: string;
    torch_version: string;
    status: 'pending' | 'installing' | 'ready' | 'error';
    error_message?: string;
}
