import { useState } from 'react';
import {
    Plus,
    Trash2,
    RefreshCw,
    Bot,
    Settings,
    AlertCircle,
    CheckCircle2,
    Info,
    ChevronRight,
    Search,
    MoreVertical,
    Download,
    Terminal,
    Play
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Card, CardHeader, CardTitle, CardContent, CardDescription, CardFooter } from '../../components/ui/card';
import { Input } from '../../components/ui/input';
import { Select } from '../../components/ui/select';
import { DropdownMenu } from '../../components/ui/dropdown-menu';
import { LoadingOverlay } from '../../components/ui/loading-overlay';
import { PageContainer } from '../../components/ui/page-container';
import { Modal } from '../../components/ui/modal';
import { MessageBox } from '../../components/ui/message-box';
import { StatusBadge } from '../../components/ui/status-badge';

export function DesignSystemPreview() {
    const [showModal, setShowModal] = useState(false);
    const [showConfirm, setShowConfirm] = useState(false);
    const [showDangerConfirm, setShowDangerConfirm] = useState(false);
    const [showSuccessMsg, setShowSuccessMsg] = useState(false);
    const [showErrorMsg, setShowErrorMsg] = useState(false);
    const [showInfoMsg, setShowInfoMsg] = useState(false);

    return (
        <PageContainer>
            <div className="space-y-12 pb-20">
                {/* Header */}
                <section className="space-y-4">
                    <h1 className="text-4xl font-bold tracking-tight text-content-primary">Design System Preview</h1>
                    <p className="text-xl text-content-secondary max-w-2xl">
                        A showcase of the unified visual language for LeroPilot.
                        This page demonstrates components, states, and the overall aesthetic.
                    </p>
                </section>

                {/* Buttons Section */}
                <section className="space-y-6">
                    <div className="border-b border-border-default pb-2">
                        <h2 className="text-2xl font-semibold text-content-primary">Buttons</h2>
                        <p className="text-content-tertiary">Standardized actions with consistent hover and active states.</p>
                    </div>

                    <div className="grid gap-8 md:grid-cols-2">
                        <div className="space-y-4">
                            <h3 className="text-sm font-medium uppercase tracking-wider text-content-tertiary">Variants</h3>
                            <div className="flex flex-wrap gap-4">
                                <Button>Primary Action</Button>
                                <Button variant="secondary">Secondary</Button>
                                <Button variant="ghost">Ghost Button</Button>
                            </div>
                        </div>

                        <div className="space-y-4">
                            <h3 className="text-sm font-medium uppercase tracking-wider text-content-tertiary">Sizes</h3>
                            <div className="flex flex-wrap items-center gap-4">
                                <Button size="sm">Small</Button>
                                <Button size="md">Medium</Button>
                                <Button size="lg">Large Scale</Button>
                            </div>
                        </div>

                        <div className="space-y-4">
                            <h3 className="text-sm font-medium uppercase tracking-wider text-content-tertiary">States</h3>
                            <div className="flex flex-wrap gap-4">
                                <Button disabled>Disabled State</Button>
                                <Button>
                                    <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                                    Processing...
                                </Button>
                            </div>
                        </div>

                        <div className="space-y-4">
                            <h3 className="text-sm font-medium uppercase tracking-wider text-content-tertiary">Icons</h3>
                            <div className="flex flex-wrap gap-4">
                                <Button><Plus className="mr-2 h-4 w-4" /> Add Robot</Button>
                                <Button variant="secondary"><Settings className="mr-2 h-4 w-4" /> Config</Button>
                                <Button variant="ghost" size="sm" className="p-0 h-10 w-10"><RefreshCw className="h-4 w-4" /></Button>
                            </div>
                        </div>
                    </div>
                </section>

                {/* Destructive Actions Section */}
                <section className="space-y-6">
                    <div className="border-b border-border-default pb-2">
                        <h2 className="text-2xl font-semibold text-content-primary">Destructive Actions</h2>
                        <p className="text-content-tertiary">Dangerous operations should use clear red/danger styling as a warning.</p>
                    </div>

                    <div className="grid gap-8 md:grid-cols-2">
                        <div className="space-y-4">
                            <h3 className="text-sm font-medium uppercase tracking-wider text-content-tertiary">Primary Danger</h3>
                            <div className="flex flex-wrap gap-4">
                                <Button variant="danger">
                                    <Trash2 className="mr-2 h-4 w-4" />
                                    Delete Environment
                                </Button>
                            </div>
                        </div>

                        <div className="space-y-4">
                            <h3 className="text-sm font-medium uppercase tracking-wider text-content-tertiary">Ghost Danger</h3>
                            <div className="flex flex-wrap gap-4">
                                <Button variant="ghost-danger">
                                    <Trash2 className="mr-2 h-4 w-4 transition-colors" />
                                    Quick Delete
                                </Button>
                                <span className="text-xs text-content-tertiary self-center">← First-class variant</span>
                            </div>
                        </div>
                    </div>
                </section>

                {/* Forms Section */}
                <section className="space-y-6">
                    <div className="border-b border-border-default pb-2">
                        <h2 className="text-2xl font-semibold text-content-primary">Forms & Selection</h2>
                        <p className="text-content-tertiary">Unified input fields and selection controls.</p>
                    </div>

                    <div className="grid gap-8 md:grid-cols-2">
                        <div className="space-y-4">
                            <h3 className="text-sm font-medium uppercase tracking-wider text-content-tertiary">Inputs</h3>
                            <div className="space-y-4">
                                <div className="space-y-2">
                                    <label className="text-sm font-medium text-content-secondary">Standard Input</label>
                                    <Input placeholder="Type something..." />
                                </div>
                                <div className="space-y-2">
                                    <label className="text-sm font-medium text-content-secondary">Search Input (Proposed)</label>
                                    <div className="relative">
                                        <Search className="absolute left-3 top-2.5 h-4 w-4 text-content-tertiary" />
                                        <Input className="pl-10" placeholder="Search devices..." />
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div className="space-y-4">
                            <h3 className="text-sm font-medium uppercase tracking-wider text-content-tertiary">Select & Dropdowns</h3>
                            <div className="space-y-4">
                                <div className="space-y-2">
                                    <label className="text-sm font-medium text-content-secondary">Standard Select</label>
                                    <Select
                                        options={[
                                            { label: 'Option 1', value: '1' },
                                            { label: 'Option 2', value: '2' },
                                            { label: 'Option 3', value: '3' },
                                        ]}
                                    />
                                </div>
                                <div className="space-y-2">
                                    <label className="text-sm font-medium text-content-secondary">Dropdown Menu (Actions)</label>
                                    <div className="flex items-center gap-4">
                                        <DropdownMenu
                                            trigger={<MoreVertical className="h-4 w-4" />}
                                            items={[
                                                { id: 'edit', label: 'Edit Info', onClick: () => { }, icon: <Settings className="h-4 w-4" /> },
                                                { id: 'logs', label: 'Open Terminal', onClick: () => { }, icon: <Terminal className="h-4 w-4" /> },
                                                { id: 'run', label: 'Run Script', onClick: () => { }, icon: <Play className="h-4 w-4" /> },
                                                { id: 'download', label: 'Download Logs', onClick: () => { }, icon: <Download className="h-4 w-4" /> },
                                                { id: 'delete', label: 'Delete Item', onClick: () => { }, variant: 'danger', icon: <Trash2 className="h-4 w-4" /> },
                                            ]}
                                        />
                                        <span className="text-xs text-content-tertiary">← Click to open</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </section>

                {/* Cards Section */}
                <section className="space-y-6">
                    <div className="border-b border-border-default pb-2">
                        <h2 className="text-2xl font-semibold text-content-primary">Cards & Surfaces</h2>
                        <p className="text-content-tertiary">Visual hierarchy for content grouping.</p>
                    </div>

                    <div className="grid gap-6 md:grid-cols-3">
                        <Card>
                            <CardHeader>
                                <CardTitle className="flex items-center gap-2">
                                    <Bot className="h-5 w-5 text-primary" />
                                    Robot Card
                                </CardTitle>
                                <CardDescription>System status and health.</CardDescription>
                            </CardHeader>
                            <CardContent>
                                <div className="space-y-2">
                                    <div className="flex justify-between text-sm">
                                        <span className="text-content-secondary">Battery</span>
                                        <span className="text-content-primary font-medium">85%</span>
                                    </div>
                                    <div className="h-2 w-full bg-surface-tertiary rounded-full overflow-hidden">
                                        <div className="h-full bg-success-icon w-[85%]" />
                                    </div>
                                </div>
                            </CardContent>
                            <CardFooter className="justify-end border-t border-border-subtle pt-4 mt-2">
                                <Button variant="ghost" size="sm">View Details</Button>
                            </CardFooter>
                        </Card>

                        <Card className="border-primary/30 bg-primary/5">
                            <CardHeader>
                                <div className="w-10 h-10 rounded-full bg-primary flex items-center justify-center text-primary-content mb-2">
                                    <Info className="h-6 w-6" />
                                </div>
                                <CardTitle>Highlighted Info</CardTitle>
                                <CardDescription>A card used to draw attention.</CardDescription>
                            </CardHeader>
                            <CardContent>
                                <p className="text-sm text-content-secondary">
                                    This variant uses a subtle primary background to indicate importance.
                                </p>
                            </CardContent>
                        </Card>

                        <Card className="hover:border-primary/50 transition-colors cursor-pointer group">
                            <CardContent className="pt-6">
                                <div className="flex items-start justify-between">
                                    <div className="space-y-1">
                                        <h3 className="font-semibold text-content-primary group-hover:text-primary transition-colors">Interactive Card</h3>
                                        <p className="text-sm text-content-secondary text-balance">
                                            Clicking this card leads to more advanced settings.
                                        </p>
                                    </div>
                                    <ChevronRight className="h-5 w-5 text-content-tertiary group-hover:translate-x-1 transition-transform" />
                                </div>
                            </CardContent>
                        </Card>
                    </div>
                </section>

                {/* Status Indicators Section */}
                <section className="space-y-6">
                    <div className="border-b border-border-default pb-2">
                        <h2 className="text-2xl font-semibold text-content-primary">Status & Alerts</h2>
                        <p className="text-content-tertiary">Providing feedback and system state.</p>
                    </div>

                    <div className="space-y-6">
                        <div className="flex flex-wrap gap-4 items-center">
                            <StatusBadge variant="success">ONLINE</StatusBadge>
                            <StatusBadge variant="success" pulse="none">ONLINE (No Pulse)</StatusBadge>
                            <StatusBadge variant="neutral">OFFLINE</StatusBadge>
                            <StatusBadge variant="warning">READY</StatusBadge>
                            <StatusBadge variant="error" pulse="fast">ERROR</StatusBadge>
                        </div>

                        <div className="grid gap-4 md:grid-cols-2">
                            <div className="p-4 rounded-lg bg-error-surface border border-error-border flex gap-3">
                                <AlertCircle className="h-5 w-5 text-error-icon shrink-0" />
                                <div className="space-y-1">
                                    <p className="text-sm font-medium text-error-content">Hardware disconnect detected</p>
                                    <p className="text-xs text-error-content/80">Please check the USB connection to your robot.</p>
                                </div>
                            </div>
                            <div className="p-4 rounded-lg bg-success-surface border border-success-border flex gap-3">
                                <CheckCircle2 className="h-5 w-5 text-success-icon shrink-0" />
                                <div className="space-y-1">
                                    <p className="text-sm font-medium text-success-content">Environment ready</p>
                                    <p className="text-xs text-success-content/80">Calibration successfully completed.</p>
                                </div>
                            </div>
                        </div>
                    </div>
                </section>

                {/* Loading Section */}
                <section className="space-y-6">
                    <div className="border-b border-border-default pb-2">
                        <h2 className="text-2xl font-semibold text-content-primary">Loading & Progress</h2>
                        <p className="text-content-tertiary">Visual feedback for asynchronous operations.</p>
                    </div>

                    <div className="grid gap-8 md:grid-cols-2">
                        <div className="space-y-4">
                            <h3 className="text-sm font-medium uppercase tracking-wider text-content-tertiary">Standard Overlays</h3>
                            <div className="grid grid-cols-2 gap-4 h-64">
                                <div className="relative bg-surface-secondary/50 rounded-xl overflow-hidden border border-border-subtle">
                                    <LoadingOverlay message="Initializing..." size="sm" fancy={false} />
                                </div>
                                <div className="relative bg-surface-secondary/50 rounded-xl overflow-hidden border border-border-subtle">
                                    <LoadingOverlay message="Loading data" subtitle="PLEASE WAIT" size="sm" />
                                </div>
                            </div>
                        </div>

                        <div className="space-y-4">
                            <h3 className="text-sm font-medium uppercase tracking-wider text-content-tertiary">Large / Fancy States</h3>
                            <div className="relative h-64 bg-surface-secondary/50 rounded-xl overflow-hidden border border-border-subtle">
                                <LoadingOverlay
                                    message="Completing Installation"
                                    subtitle="CONFIGURING HARDWARE PARAMETERS..."
                                    size="lg"
                                    fancy={true}
                                />
                            </div>
                        </div>
                    </div>
                </section>

                {/* Dialogs & Modals Section */}
                <section className="space-y-6">
                    <div className="border-b border-border-default pb-2">
                        <h2 className="text-2xl font-semibold text-content-primary">Dialogs & Modals</h2>
                        <p className="text-content-tertiary">Overlay windows for focused tasks or critical confirmations.</p>
                    </div>

                    <div className="grid gap-8 md:grid-cols-2">
                        <div className="space-y-4">
                            <h3 className="text-sm font-medium uppercase tracking-wider text-content-tertiary">Standard Modal</h3>
                            <div className="flex flex-wrap gap-4">
                                <Button onClick={() => setShowModal(true)}>
                                    Open Modal
                                </Button>
                            </div>
                            <p className="text-sm text-content-secondary">
                                Used for complex content, forms, or settings that require focus.
                            </p>
                        </div>

                        <div className="space-y-4">
                            <h3 className="text-sm font-medium uppercase tracking-wider text-content-tertiary">Confirm & Message Dialogs</h3>
                            <div className="flex flex-wrap gap-4">
                                <Button variant="secondary" onClick={() => setShowConfirm(true)}>
                                    Trigger Action
                                </Button>
                                <Button variant="danger" onClick={() => setShowDangerConfirm(true)}>
                                    Delete Item
                                </Button>
                                <Button variant="secondary" onClick={() => setShowSuccessMsg(true)}>
                                    Success Message
                                </Button>
                                <Button variant="secondary" onClick={() => setShowErrorMsg(true)}>
                                    Error Message
                                </Button>
                                <Button variant="secondary" onClick={() => setShowInfoMsg(true)}>
                                    Info Message
                                </Button>
                            </div>
                            <p className="text-sm text-content-secondary">
                                Used for quick confirmations, alerts, or destructive actions.
                            </p>
                        </div>
                    </div>
                </section>
            </div>

            {/* Demo Dialogs */}
            <Modal
                isOpen={showModal}
                onClose={() => setShowModal(false)}
                title="Example Modal"
            >
                <div className="space-y-4">
                    <p className="text-content-secondary">
                        This is a standard modal dialog. It should be used when you need to display content
                        that requires the user's focus, but isn't necessarily a critical confirmation.
                    </p>
                    <div className="p-4 bg-surface-tertiary rounded-lg border border-border-subtle">
                        <p className="text-sm font-mono text-content-primary">
                            Modals handle their own scroll behavior and backdrop.
                        </p>
                    </div>
                    <div className="flex justify-end gap-3 pt-4">
                        <Button variant="ghost" onClick={() => setShowModal(false)}>Close</Button>
                        <Button onClick={() => setShowModal(false)}>Save Changes</Button>
                    </div>
                </div>
            </Modal>

            <MessageBox
                isOpen={showConfirm}
                onClose={() => setShowConfirm(false)}
                title="Confirm Action"
                message="Are you sure you want to proceed with this action?"
                description="This is a standard confirmation request using MessageBox."
                buttonType="ok-cancel"
                onConfirm={() => setShowConfirm(false)}
                onCancel={() => setShowConfirm(false)}
            />

            <MessageBox
                isOpen={showDangerConfirm}
                onClose={() => setShowDangerConfirm(false)}
                type="warning"
                title="Delete Resource"
                message="Are you sure you want to proceed?"
                description="This action cannot be undone. This will permanently delete the selected resource."
                confirmText="Delete"
                buttonType="ok-cancel"
                onConfirm={() => setShowDangerConfirm(false)}
                onCancel={() => setShowDangerConfirm(false)}
            />

            <MessageBox
                isOpen={showSuccessMsg}
                onClose={() => setShowSuccessMsg(false)}
                type="success"
                message="Operation Successful"
                description="The task has been completed successfully and all changes were saved."
            />

            <MessageBox
                isOpen={showErrorMsg}
                onClose={() => setShowErrorMsg(false)}
                type="error"
                message="Save Failed"
                description="An unexpected error occurred while trying to save the configuration. Please try again."
            />

            <MessageBox
                isOpen={showInfoMsg}
                onClose={() => setShowInfoMsg(false)}
                type="info"
                message="Update Available"
                description="A new version of the software is available. Would you like to update now?"
                buttonType="yes-no"
            />
        </PageContainer>
    );
}
