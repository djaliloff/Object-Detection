import React, { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  Plus, 
  Search, 
  Trash2, 
  RefreshCcw, 
  Monitor, 
  Settings,
  Shield,
  List,
  ChevronDown,
  LayoutGrid,
  Layers
} from 'lucide-react';
import toast from 'react-hot-toast';

import CameraModal from '../components/CameraModal';
import { camerasAPI } from '../utils/api';

const CameraConfiguration = () => {
  const queryClient = useQueryClient();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingCamera, setEditingCamera] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [viewType, setViewType] = useState('grid');
  const [statusFilter, setStatusFilter] = useState('all');
  const [modalityFilter, setModalityFilter] = useState('all');
  const [selectedCameras, setSelectedCameras] = useState([]);

  // Fetch cameras
  const { data: cameras, isLoading } = useQuery({
    queryKey: ['cameras'],
    queryFn: camerasAPI.getCameras,
  });

  // Delete camera mutation
  const deleteMutation = useMutation({
    mutationFn: (id) => camerasAPI.deleteCamera(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cameras'] });
      toast.success('Camera decommissioned');
    },
  });

  // Bulk actions
  const handleBulkDelete = () => {
    if (window.confirm(`Are you sure you want to delete ${selectedCameras.length} cameras?`)) {
      selectedCameras.forEach(id => deleteMutation.mutate(id));
      setSelectedCameras([]);
    }
  };

  const filteredCameras = useMemo(() => {
    if (!cameras) return [];
    return cameras.filter(camera => {
      const nameMatch = camera.name?.toLowerCase().includes(searchQuery.toLowerCase());
      const ipMatch = camera.ip?.includes(searchQuery);
      const matchesSearch = nameMatch || ipMatch;
      const matchesStatus = statusFilter === 'all' || camera.status === statusFilter;
      const matchesModality = modalityFilter === 'all' || camera.modality === modalityFilter;
      return matchesSearch && matchesStatus && matchesModality;
    });
  }, [cameras, searchQuery, statusFilter, modalityFilter]);

  const toggleCameraSelection = (id) => {
    setSelectedCameras(prev => 
      prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]
    );
  };

  const handleEdit = (camera) => {
    setEditingCamera(camera);
    setIsModalOpen(true);
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-4">
        <div className="w-12 h-12 border-4 border-blue-500/20 border-t-blue-500 rounded-full animate-spin" />
        <p className="text-neutral-500 font-bold uppercase tracking-widest text-xs">Syncing nodes...</p>
      </div>
    );
  }

  return (
    <div className="p-4 lg:p-8 bg-[#0a0a0c] min-h-screen text-neutral-200">
      {/* Header & Controls */}
      <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-6 mb-8">
        <div>
           <div className="flex items-center space-x-3 mb-1">
              <div className="p-2 bg-blue-600/20 rounded-lg border border-blue-500/30">
                <Shield className="w-6 h-6 text-blue-400" />
              </div>
              <h1 className="text-3xl font-black bg-gradient-to-r from-white to-white/60 bg-clip-text text-transparent">
                Camera Configuration
              </h1>
            </div>
          <p className="text-neutral-500 font-medium">Managing {cameras?.length || 0} endpoints across the network</p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {selectedCameras.length > 0 && (
            <button 
              onClick={handleBulkDelete}
              className="flex items-center space-x-2 px-4 py-2.5 bg-red-500/10 text-red-400 border border-red-500/30 rounded-xl font-bold text-sm hover:bg-red-500/20 transition-all"
            >
              <Trash2 className="w-4 h-4" />
              <span>Detach {selectedCameras.length}</span>
            </button>
          )}

          <button
            onClick={() => {
              setEditingCamera(null);
              setIsModalOpen(true);
            }}
            className="flex items-center space-x-2 px-6 py-2.5 bg-blue-600 text-white rounded-xl font-bold shadow-lg shadow-blue-600/25 hover:bg-blue-500 transition-all active:scale-95"
          >
            <Plus className="w-5 h-5" />
            <span>Deploy Camera</span>
          </button>
        </div>
      </div>

      {/* Advanced Filters */}
      <div className="bg-neutral-900/40 border border-white/5 rounded-3xl p-6 backdrop-blur-2xl mb-8 space-y-6 shadow-inner">
        <div className="flex flex-col lg:flex-row gap-4">
          <div className="relative flex-1 group">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-neutral-600 group-focus-within:text-blue-500 transition-colors" />
            <input
              type="text"
              placeholder="Search by name, IP, or location..."
              className="w-full bg-neutral-800/50 border border-white/5 rounded-2xl py-3 pl-12 pr-4 outline-none focus:ring-2 ring-blue-500/50 transition-all text-neutral-200 placeholder:text-neutral-600 font-medium"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>

          <div className="flex gap-2">
            <div className="relative">
              <select
                className="appearance-none bg-neutral-800/50 border border-white/5 rounded-2xl py-3 pl-4 pr-10 outline-none focus:ring-2 ring-blue-500/50 transition-all text-neutral-300 font-bold text-sm min-w-[140px]"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
              >
                <option value="all">Status: All</option>
                <option value="online">Online</option>
                <option value="offline">Offline</option>
              </select>
              <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-500 pointer-events-none" />
            </div>

            <div className="relative">
              <select
                className="appearance-none bg-neutral-800/50 border border-white/5 rounded-2xl py-3 pl-4 pr-10 outline-none focus:ring-2 ring-blue-500/50 transition-all text-neutral-300 font-bold text-sm min-w-[140px]"
                value={modalityFilter}
                onChange={(e) => setModalityFilter(e.target.value)}
              >
                <option value="all">Type: All</option>
                <option value="rgb">RGB</option>
                <option value="thermal">Thermal</option>
                <option value="fused">Fused</option>
              </select>
              <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-500 pointer-events-none" />
            </div>

            <div className="flex bg-neutral-800/50 p-1 rounded-2xl border border-white/5">
              <button 
                onClick={() => setViewType('grid')}
                className={`p-2 rounded-xl transition-all ${viewType === 'grid' ? 'bg-blue-600 text-white shadow-lg' : 'text-neutral-500 hover:text-white'}`}
              >
                <LayoutGrid className="w-5 h-5" />
              </button>
              <button 
                onClick={() => setViewType('list')}
                className={`p-2 rounded-xl transition-all ${viewType === 'list' ? 'bg-blue-600 text-white shadow-lg' : 'text-neutral-500 hover:text-white'}`}
              >
                <List className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Camera Grid/List */}
      {viewType === 'grid' ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          {filteredCameras.map((camera) => (
            <div 
              key={camera.id}
              className={`group relative bg-neutral-900/40 border rounded-[32px] p-6 backdrop-blur-2xl transition-all hover:bg-neutral-800/60 hover:-translate-y-1 ${
                selectedCameras.includes(camera.id) ? 'border-blue-500/50 ring-2 ring-blue-500/20' : 'border-white/5'
              }`}
            >
              <div className="flex justify-between items-start mb-6">
                <div className="flex items-center space-x-4">
                  <div className={`p-3 rounded-2xl ${camera.status === 'online' ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'}`}>
                    <Monitor className="w-6 h-6" />
                  </div>
                  <div>
                    <h3 className="text-xl font-bold text-white group-hover:text-blue-400 transition-colors uppercase tracking-tight">{camera.name}</h3>
                    <div className="flex items-center space-x-2 mt-1">
                      <div className={`w-2 h-2 rounded-full ${camera.status === 'online' ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
                      <span className="text-xs font-bold text-neutral-500 tracking-wider uppercase">{camera.status}</span>
                    </div>
                  </div>
                </div>
                <input 
                  type="checkbox"
                  checked={selectedCameras.includes(camera.id)}
                  onChange={() => toggleCameraSelection(camera.id)}
                  className="w-5 h-5 border-2 border-white/5 rounded-lg bg-neutral-800 accent-blue-600 cursor-pointer"
                />
              </div>

              <div className="grid grid-cols-2 gap-4 mb-6">
                <div className="p-4 bg-white/5 rounded-2xl border border-white/5">
                  <p className="text-[10px] font-black uppercase tracking-widest text-neutral-600 mb-1">Network</p>
                  <p className="text-sm font-bold text-white truncate">{camera.ip || '---'}</p>
                </div>
                <div className="p-4 bg-white/5 rounded-2xl border border-white/5">
                  <p className="text-[10px] font-black uppercase tracking-widest text-neutral-600 mb-1">Optics</p>
                  <p className="text-sm font-bold text-white uppercase">{camera.modality}</p>
                </div>
              </div>

              <div className="flex items-center space-x-2">
                <button 
                  onClick={() => handleEdit(camera)}
                  className="flex-1 px-4 py-2.5 bg-neutral-800 hover:bg-neutral-700 text-white rounded-xl font-bold text-sm border border-white/5 transition-all"
                >
                  Configure
                </button>
                <button 
                  onClick={() => deleteMutation.mutate(camera.id)}
                  className="px-4 py-2.5 bg-red-500/10 hover:bg-red-500/20 text-red-400 rounded-xl transition-all border border-red-500/10"
                >
                  <Trash2 className="w-5 h-5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="bg-neutral-900/40 border border-white/5 rounded-3xl overflow-hidden backdrop-blur-2xl">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-white/5 text-[10px] uppercase font-black tracking-widest text-neutral-600">
                <th className="px-6 py-4">
                   <input 
                      type="checkbox"
                      checked={selectedCameras.length === filteredCameras.length}
                      onChange={() => setSelectedCameras(selectedCameras.length === filteredCameras.length ? [] : filteredCameras.map(c => c.id))}
                      className="w-4 h-4 rounded bg-neutral-800 border-white/5 accent-blue-600"
                    />
                </th>
                <th className="px-6 py-4">Identity</th>
                <th className="px-6 py-4">Address</th>
                <th className="px-6 py-4">Mechanism</th>
                <th className="px-6 py-4">Uptime Status</th>
                <th className="px-6 py-4 text-right">Ops</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {filteredCameras.map((camera) => (
                <tr key={camera.id} className="hover:bg-white/[0.02] transition-colors group">
                  <td className="px-6 py-4">
                    <input 
                      type="checkbox"
                      checked={selectedCameras.includes(camera.id)}
                      onChange={() => toggleCameraSelection(camera.id)}
                      className="w-4 h-4 rounded bg-neutral-800 border-white/5 accent-blue-600 cursor-pointer"
                    />
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center space-x-3">
                      <div className={`p-2 rounded-lg ${camera.status === 'online' ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'}`}>
                        <Monitor className="w-4 h-4" />
                      </div>
                      <span className="font-bold text-white uppercase tracking-tight">{camera.name}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4 font-mono text-sm text-neutral-400">{camera.ip || 'DNS Linked'}</td>
                  <td className="px-6 py-4">
                    <span className="px-2.5 py-1 bg-blue-500/10 text-blue-400 rounded-lg text-[10px] font-black uppercase tracking-widest border border-blue-500/20">
                      {camera.modality}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center space-x-2">
                      <div className={`w-2 h-2 rounded-full ${camera.status === 'online' ? 'bg-green-500' : 'bg-red-500'}`} />
                      <span className="text-xs font-bold text-neutral-300 uppercase">{camera.status}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <div className="flex items-center justify-end space-x-2">
                      <button onClick={() => handleEdit(camera)} className="p-2 text-neutral-500 hover:text-white transition-colors">
                        <Settings className="w-5 h-5" />
                      </button>
                      <button onClick={() => deleteMutation.mutate(camera.id)} className="p-2 text-neutral-500 hover:text-red-400 transition-colors">
                        <Trash2 className="w-5 h-5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Empty State */}
      {filteredCameras.length === 0 && (
        <div className="flex flex-col items-center justify-center py-32 space-y-6">
          <div className="p-8 bg-neutral-900 border border-white/5 rounded-full">
            <Layers className="w-16 h-16 text-neutral-800" />
          </div>
          <div className="text-center">
            <h3 className="text-xl font-bold text-white mb-2 uppercase tracking-wide">No Deployments Found</h3>
            <p className="text-neutral-500 max-w-sm">No cameras match your current tactical filters. Try adjusting your parameters or deploy a new node.</p>
          </div>
          <button 
            onClick={() => {setSearchQuery(''); setStatusFilter('all'); setModalityFilter('all');}}
            className="flex items-center space-x-2 px-6 py-2.5 bg-neutral-800 border border-white/10 rounded-xl font-bold text-white hover:bg-neutral-700 transition-all"
          >
            <RefreshCcw className="w-5 h-5" />
            <span>Reset Matrix</span>
          </button>
        </div>
      )}

      <CameraModal 
        isOpen={isModalOpen}
        onClose={() => {
          setIsModalOpen(false);
          setEditingCamera(null);
        }}
        camera={editingCamera}
      />
    </div>
  );
};

export default CameraConfiguration;
