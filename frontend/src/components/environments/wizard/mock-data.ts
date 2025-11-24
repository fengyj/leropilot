export const MOCK_REPOS = [
  {
    id: 'official',
    name: 'LeRobot (Official)',
    url: 'https://github.com/huggingface/lerobot',
    isDownloaded: true,
    lastUpdated: '2024-11-23T10:00:00Z',
  },
  {
    id: 'custom-1',
    name: 'My Custom Fork',
    url: 'https://github.com/user/lerobot-fork',
    isDownloaded: false,
    lastUpdated: null,
  },
];

export const MOCK_VERSIONS = [
  { id: 'v0.4.1', name: 'v0.4.1', type: 'tag', date: '2024-11-20' },
  { id: 'v0.4.0', name: 'v0.4.0', type: 'tag', date: '2024-11-15' },
  { id: 'v0.3.3', name: 'v0.3.3', type: 'tag', date: '2024-10-01' },
  { id: 'main', name: 'main', type: 'branch', date: '2024-11-23' },
];

export const MOCK_EXTRAS = [
  {
    id: 'aloha',
    name: 'ALOHA',
    description: 'ALOHA robot support',
    category: 'robots',
  },
  {
    id: 'pusht',
    name: 'PushT',
    description: 'PushT robot support',
    category: 'robots',
  },
  {
    id: 'reachy2',
    name: 'Reachy 2',
    description: 'Reachy 2 robot support',
    category: 'robots',
  },
  { id: 'xarm', name: 'xArm', description: 'xArm robot support', category: 'robots' },
  { id: 'pi0', name: 'Pi0', description: 'Pi0 robot support', category: 'robots' },
  { id: 'gym', name: 'Gym', description: 'OpenAI Gym support', category: 'simulation' },
  { id: 'dev', name: 'Dev Tools', description: 'Development tools', category: 'other' },
];
