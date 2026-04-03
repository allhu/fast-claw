<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import axios from 'axios'

interface Contact {
  email: string | null;
  phone: string | null;
  instagram: string | null;
  facebook: string | null;
  whatsapp: string | null;
}

interface Store {
  id: number;
  url: string;
  source: string;
  status: string;
  created_at: string;
  contacts: Contact[];
}

interface Task {
  id: number;
  task_type: string;
  status: string;
  parameters: string | null;
  result_summary: string | null;
  progress_text: string | null;
  current_keyword: string | null;
  items_found: number;
  items_saved: number;
  created_at: string;
  completed_at: string | null;
}

interface Keyword {
  id: number;
  word: string;
  source: string;
  is_active: boolean;
  schedule_interval: string;
  current_status: string;
  last_run_at: string | null;
  next_run_at: string | null;
  created_at: string;
}

const stores = ref<Store[]>([])
const tasks = ref<Task[]>([])
const keywords = ref<Keyword[]>([])
const loading = ref(true)
const currentTab = ref('stores') // 'stores', 'tasks', or 'keywords'

// Task Form state
const showTaskModal = ref(false)
const newTaskType = ref('scrape_contacts')
const newTaskParams = ref('')
const generatingKeywords = ref(false)
const fbApiToken = ref('')
const fbCountry = ref('US')
const fbMaxPages = ref(2)

// Keyword Form state
const showKeywordModal = ref(false)
const newKeywordWord = ref('')
const newKeywordInterval = ref('weekly')

// Pagination state
const currentPage = ref(1)
const pageSize = ref(100)
const totalStores = ref(0)
const channelStats = ref<Array<{
  channel: string,
  links_found: number,
  stores_saved: number,
  efficiency: number,
  avg_per_kw: number
}>>([])
const storeStatusFilter = ref('all') // 'all', 'pending', 'completed'

const fetchStats = async () => {
  try {
    const response = await axios.get(`http://127.0.0.1:8000/api/stats/channels`)
    channelStats.value = response.data
  } catch (error) {
    console.error('Error fetching channel stats:', error)
  }
}

const fetchStores = async () => {
  try {
    loading.value = true
    const skip = (currentPage.value - 1) * pageSize.value
    const response = await axios.get(`http://127.0.0.1:8000/api/stores?skip=${skip}&limit=${pageSize.value}&status=${storeStatusFilter.value}`)
    stores.value = response.data.items
    totalStores.value = response.data.total
  } catch (error) {
    console.error('Failed to fetch stores:', error)
  } finally {
    loading.value = false
  }
}

// Watch for filter changes to reset page and refetch
watch(storeStatusFilter, () => {
  currentPage.value = 1
  fetchStores()
})

const exportStores = () => {
  const url = `http://127.0.0.1:8000/api/stores/export?status=${storeStatusFilter.value}`
  window.open(url, '_blank')
}

const deleteStore = async (id: number) => {
  if (!confirm('Are you sure you want to delete this store and its contacts?')) return;
  try {
    await axios.delete(`http://127.0.0.1:8000/api/stores/${id}`)
    await fetchStores()
  } catch (error) {
    console.error('Failed to delete store:', error)
    alert('Failed to delete store')
  }
}

const fetchTasks = async () => {
  try {
    const response = await axios.get('http://127.0.0.1:8000/api/tasks')
    tasks.value = response.data
  } catch (error) {
    console.error('Failed to fetch tasks:', error)
  }
}

const deleteTask = async (id: number) => {
  if (!confirm('Are you sure you want to delete this task record?')) return;
  try {
    await axios.delete(`http://127.0.0.1:8000/api/tasks/${id}`)
    await fetchTasks()
  } catch (error) {
    console.error('Failed to delete task:', error)
    alert('Failed to delete task')
  }
}

const stopTask = async (id: number) => {
  try {
    await axios.post(`http://127.0.0.1:8000/api/tasks/${id}/stop`)
    await fetchTasks()
  } catch (error) {
    console.error('Failed to stop task:', error)
    alert('Failed to stop task')
  }
}

const restartTask = async (id: number) => {
  try {
    await axios.post(`http://127.0.0.1:8000/api/tasks/${id}/restart`)
    await fetchTasks()
  } catch (error) {
    console.error('Failed to restart task:', error)
    alert('Failed to restart task')
  }
}

const fetchKeywords = async () => {
  try {
    const response = await axios.get('http://127.0.0.1:8000/api/keywords')
    keywords.value = response.data
  } catch (error) {
    console.error('Failed to fetch keywords:', error)
  }
}

const triggerAutomation = async () => {
  if (!confirm('This will force the background system to run all automation checks right now (AI expansion, URL searching, Contact scraping). Continue?')) return;
  try {
    await axios.post('http://127.0.0.1:8000/api/system/run_scheduler')
    alert('Automation triggered successfully! Check the Tasks & Scrapers tab for running jobs.')
    setTimeout(() => {
      fetchKeywords()
      if (currentTab.value === 'tasks') fetchTasks()
    }, 2000)
  } catch (error) {
    console.error('Failed to trigger automation:', error)
    alert('Failed to trigger automation')
  }
}

const addKeyword = async () => {
  if (!newKeywordWord.value.trim()) return;
  
  // Support comma-separated multiple keywords
  const words = newKeywordWord.value.split(',').map(w => w.trim()).filter(Boolean);
  
  try {
    for (const word of words) {
      try {
        await axios.post('http://127.0.0.1:8000/api/keywords', {
          word: word,
          schedule_interval: newKeywordInterval.value,
          source: 'manual'
        })
      } catch (e) {
        console.warn(`Keyword ${word} might already exist or failed.`, e)
      }
    }
    showKeywordModal.value = false
    newKeywordWord.value = ''
    await fetchKeywords()
  } catch (error) {
    console.error('Failed to add keywords:', error)
    alert('Failed to add some keywords. They might already exist.')
  }
}

const deleteKeyword = async (id: number) => {
  if (!confirm('Are you sure you want to delete this automated keyword?')) return;
  try {
    await axios.delete(`http://127.0.0.1:8000/api/keywords/${id}`)
    await fetchKeywords()
  } catch (error) {
    console.error('Failed to delete keyword:', error)
  }
}

const toggleKeyword = async (id: number) => {
  try {
    await axios.put(`http://127.0.0.1:8000/api/keywords/${id}/toggle`)
    await fetchKeywords()
  } catch (error) {
    console.error('Failed to toggle keyword:', error)
  }
}

// Watch for tab changes to fetch data
watch(currentTab, () => {
  loadData()
})

const loadData = async () => {
  if (currentTab.value === 'stores') {
    await fetchStores()
  } else if (currentTab.value === 'tasks') {
    await fetchTasks()
  } else if (currentTab.value === 'keywords') {
    await fetchKeywords()
  } else if (currentTab.value === 'stats') {
    await fetchStats()
    // also fetch total stores count for percentages
    try {
      const response = await axios.get('http://127.0.0.1:8000/api/stores?limit=1')
      totalStores.value = response.data.total
    } catch (e) {
      console.error(e)
    }
  }
}

const generateKeywords = async () => {
  if (!newTaskParams.value.trim()) {
    alert('Please enter at least one base keyword first.')
    return
  }
  
  try {
    generatingKeywords.value = true
    const response = await axios.post('http://127.0.0.1:8000/api/generate_keywords', {
      base_keywords: newTaskParams.value
    })
    
    // Append or replace? Let's append with a comma if not empty
    const newKeywords = response.data.keywords
    if (newTaskParams.value.trim()) {
      newTaskParams.value = newTaskParams.value.trim() + ', ' + newKeywords
    } else {
      newTaskParams.value = newKeywords
    }
  } catch (error: any) {
    if (error.response && error.response.data && error.response.data.detail) {
      alert('AI Generation Failed: ' + error.response.data.detail)
    } else {
      alert('Failed to generate keywords. Please check your network and API key.')
    }
    console.error(error)
  } finally {
    generatingKeywords.value = false
  }
}

const submitTask = async () => {
  try {
    let params: any = null;
    if (newTaskType.value !== 'scrape_contacts' && newTaskParams.value) {
      // Very basic parser for comma separated values for demo purposes
      const items = newTaskParams.value.split(',').map(s => s.trim()).filter(Boolean);
      if (newTaskType.value === 'google_search') {
         params = { queries: items, max_pages: 2 };
      } else if (newTaskType.value === 'fb_ads' || newTaskType.value === 'tiktok_ads' || newTaskType.value === 'all_channels') {
         params = { 
           keywords: items, 
           max_scrolls: Number(fbMaxPages.value) || 3, // Used as scrolls for playwright 
           max_pages: Number(fbMaxPages.value) || 2,   // Used as pages for API
           country: fbCountry.value || 'US'
         };
         if ((newTaskType.value === 'fb_ads' || newTaskType.value === 'all_channels') && fbApiToken.value.trim()) {
           params.fb_token = fbApiToken.value.trim();
         }
      }
    }

    await axios.post('http://127.0.0.1:8000/api/tasks', {
      task_type: newTaskType.value,
      parameters: params
    })
    showTaskModal.value = false
    newTaskParams.value = ''
    if (currentTab.value === 'tasks') fetchTasks()
  } catch (error) {
    alert('Failed to start task')
    console.error(error)
  }
}

const exportCSV = () => {
  window.open('http://127.0.0.1:8000/api/stores/export', '_blank')
}

const nowTime = ref(new Date().getTime());

const calculateRunningTime = (task: Task) => {
  // task.created_at comes from backend in UTC ("2026-03-31 10:32:17" format string usually)
  // we need to ensure it's parsed as UTC so it doesn't offset by local timezone
  let startStr = task.created_at;
  if (!startStr.endsWith('Z') && !startStr.includes('+')) {
    startStr += 'Z';
  }
  
  const start = new Date(startStr).getTime();
  
  let end = nowTime.value;
  if (task.completed_at) {
    let endStr = task.completed_at;
    if (!endStr.endsWith('Z') && !endStr.includes('+')) {
      endStr += 'Z';
    }
    end = new Date(endStr).getTime();
  }
  
  const diffMs = end - start;
  
  // If diff is negative due to slight clock sync issues, show 0
  if (diffMs < 0) return '0s';
  
  const diffSecs = Math.floor(diffMs / 1000);
  const minutes = Math.floor(diffSecs / 60);
  const seconds = diffSecs % 60;
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  
  if (hours > 0) {
    return `${hours}h ${remainingMinutes}m ${seconds}s`;
  }
  if (minutes > 0) {
    return `${minutes}m ${seconds}s`;
  }
  return `${seconds}s`;
}

onMounted(() => {
  loadData()
  
  // Update time for running duration display
  setInterval(() => {
    nowTime.value = new Date().getTime();
  }, 1000);
  
  // Refresh data periodically depending on the active tab
  setInterval(() => {
    if (currentTab.value === 'tasks') fetchTasks();
    if (currentTab.value === 'keywords') fetchKeywords();
  }, 5000);
})
</script>

<template>
  <div class="min-h-screen bg-gray-50 p-8">
    <div class="max-w-7xl mx-auto">
      <div class="flex justify-between items-center mb-8">
        <div>
          <h1 class="text-3xl font-bold text-gray-900">FastClaw Dashboard</h1>
          <div class="mt-4 space-x-4">
            <button @click="currentTab = 'stores'; loadData()" :class="currentTab === 'stores' ? 'text-indigo-600 border-b-2 border-indigo-600' : 'text-gray-500'" class="pb-2 font-medium">Stores</button>
            <button @click="currentTab = 'tasks'; loadData()" :class="currentTab === 'tasks' ? 'text-indigo-600 border-b-2 border-indigo-600' : 'text-gray-500'" class="pb-2 font-medium">Tasks & Scrapers</button>
            <button @click="currentTab = 'keywords'; loadData()" :class="currentTab === 'keywords' ? 'text-indigo-600 border-b-2 border-indigo-600' : 'text-gray-500'" class="pb-2 font-medium">Automation</button>
            <button @click="currentTab = 'stats'; loadData()" :class="currentTab === 'stats' ? 'text-indigo-600 border-b-2 border-indigo-600' : 'text-gray-500'" class="pb-2 font-medium">Analytics</button>
          </div>
        </div>
        
        <div class="space-x-4" v-if="currentTab === 'stores'">
          <button @click="fetchStores" class="bg-white px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 hover:bg-gray-50">
            Refresh
          </button>
          <button @click="exportCSV" class="bg-indigo-600 px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white hover:bg-indigo-700">
            Export CSV
          </button>
        </div>

        <div class="space-x-4" v-if="currentTab === 'tasks'">
          <button @click="fetchTasks" class="bg-white px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 hover:bg-gray-50">
            Refresh
          </button>
          <button @click="showTaskModal = true" class="bg-indigo-600 px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white hover:bg-indigo-700">
            + New Task
          </button>
        </div>

        <div class="space-x-4" v-if="currentTab === 'keywords'">
          <button @click="triggerAutomation" class="bg-indigo-100 px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-indigo-700 hover:bg-indigo-200">
            ⚡️ Force Run Automation
          </button>
          <button @click="fetchKeywords" class="bg-white px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 hover:bg-gray-50">
            Refresh
          </button>
          <button @click="showKeywordModal = true" class="bg-indigo-600 px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white hover:bg-indigo-700">
            + Add Keyword
          </button>
        </div>
      </div>

      <!-- Stores Table -->
      <div v-if="currentTab === 'stores'" class="bg-white shadow-sm ring-1 ring-gray-900/5 sm:rounded-xl overflow-hidden flex flex-col">
        <!-- Toolbar -->
        <div class="px-4 py-3 border-b border-gray-200 bg-gray-50 flex justify-between items-center sm:px-6">
          <div class="flex items-center space-x-4">
            <label for="status-filter" class="text-sm font-medium text-gray-700">Filter by Status:</label>
            <select 
              id="status-filter" 
              v-model="storeStatusFilter"
              class="block w-40 rounded-md border-gray-300 py-1.5 pl-3 pr-10 text-gray-900 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
            >
              <option value="all">All Stores</option>
              <option value="pending">Pending</option>
              <option value="completed">Success (Found Contacts)</option>
              <option value="failed">Failed (No Contacts)</option>
            </select>
          </div>
          <button 
            @click="exportStores"
            class="inline-flex items-center px-3 py-1.5 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500"
          >
            Export CSV
          </button>
        </div>

        <div v-if="loading" class="p-8 text-center text-gray-500">Loading data...</div>
        <div v-else>
          <table class="min-w-full divide-y divide-gray-300">
          <thead class="bg-gray-50">
            <tr>
              <th scope="col" class="py-3.5 pl-4 pr-3 text-left text-sm font-semibold text-gray-900 sm:pl-6">ID</th>
              <th scope="col" class="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Store URL</th>
              <th scope="col" class="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Source</th>
              <th scope="col" class="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Status</th>
              <th scope="col" class="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Email</th>
              <th scope="col" class="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Phone</th>
              <th scope="col" class="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Social</th>
              <th scope="col" class="relative py-3.5 pl-3 pr-4 sm:pr-6">
                <span class="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-200 bg-white">
            <tr v-for="store in stores" :key="store.id" class="hover:bg-gray-50">
              <td class="whitespace-nowrap py-4 pl-4 pr-3 text-sm font-medium text-gray-900 sm:pl-6">{{ store.id }}</td>
              <td class="whitespace-nowrap px-3 py-4 text-sm text-indigo-600">
                <a :href="store.url" target="_blank" class="hover:underline">{{ store.url }}</a>
              </td>
              <td class="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                <span class="inline-flex items-center rounded-md bg-gray-100 px-2 py-1 text-xs font-medium text-gray-600">
                  {{ store.source }}
                </span>
              </td>
              <td class="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                <span :class="[
                  'inline-flex items-center rounded-md px-2 py-1 text-xs font-medium',
                  store.status === 'completed' ? 'bg-green-100 text-green-700' : 
                  store.status === 'pending' ? 'bg-yellow-100 text-yellow-800' : 'bg-gray-100 text-gray-800'
                ]">
                  {{ store.status }}
                </span>
              </td>
              <td class="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                {{ store.contacts[0]?.email || '-' }}
              </td>
              <td class="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                {{ store.contacts[0]?.phone || '-' }}
              </td>
              <td class="whitespace-nowrap px-3 py-4 text-sm text-gray-500 space-x-2">
                <a v-if="store.contacts[0]?.instagram" :href="store.contacts[0].instagram" target="_blank" title="Instagram">📸</a>
                <a v-if="store.contacts[0]?.facebook" :href="store.contacts[0].facebook" target="_blank" title="Facebook">📘</a>
                <a v-if="store.contacts[0]?.whatsapp" :href="store.contacts[0].whatsapp" target="_blank" title="WhatsApp">💬</a>
                <span v-if="!store.contacts[0]?.instagram && !store.contacts[0]?.facebook && !store.contacts[0]?.whatsapp">-</span>
              </td>
              <td class="relative whitespace-nowrap py-4 pl-3 pr-4 text-right text-sm font-medium sm:pr-6">
                <button @click="deleteStore(store.id)" class="text-red-600 hover:text-red-900">Delete</button>
              </td>
            </tr>
            <tr v-if="stores.length === 0">
              <td colspan="8" class="px-3 py-8 text-center text-sm text-gray-500">No stores found.</td>
            </tr>
          </tbody>
        </table>
        
        <!-- Pagination Controls -->
        <div class="bg-white px-4 py-3 flex items-center justify-between border-t border-gray-200 sm:px-6">
          <div class="hidden sm:flex-1 sm:flex sm:items-center sm:justify-between">
            <div>
              <p class="text-sm text-gray-700">
                Showing
                <span class="font-medium">{{ (currentPage - 1) * pageSize + 1 }}</span>
                to
                <span class="font-medium">{{ Math.min(currentPage * pageSize, totalStores) }}</span>
                of
                <span class="font-medium">{{ totalStores }}</span>
                results
              </p>
            </div>
            <div>
              <nav class="relative z-0 inline-flex rounded-md shadow-sm -space-x-px" aria-label="Pagination">
                <button 
                  @click="currentPage > 1 ? (currentPage--, fetchStores()) : null"
                  :disabled="currentPage === 1"
                  class="relative inline-flex items-center px-2 py-2 rounded-l-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50"
                >
                  Previous
                </button>
                <button 
                  @click="currentPage * pageSize < totalStores ? (currentPage++, fetchStores()) : null"
                  :disabled="currentPage * pageSize >= totalStores"
                  class="relative inline-flex items-center px-2 py-2 rounded-r-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50"
                >
                  Next
                </button>
              </nav>
            </div>
          </div>
        </div>
        </div>
      </div>

      <!-- Tasks Table -->
      <div v-if="currentTab === 'tasks'" class="bg-white shadow-sm ring-1 ring-gray-900/5 sm:rounded-xl overflow-hidden">
        <div v-if="loading" class="p-8 text-center text-gray-500">Loading data...</div>
        <table v-else class="min-w-full divide-y divide-gray-300">
          <thead class="bg-gray-50">
            <tr>
              <th scope="col" class="py-3.5 pl-4 pr-3 text-left text-sm font-semibold text-gray-900 sm:pl-6">ID</th>
              <th scope="col" class="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Task Type</th>
              <th scope="col" class="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Status</th>
              <th scope="col" class="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Progress</th>
              <th scope="col" class="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Summary</th>
              <th scope="col" class="relative py-3.5 pl-3 pr-4 sm:pr-6">
                <span class="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-200 bg-white">
            <tr v-for="task in tasks" :key="task.id" class="hover:bg-gray-50">
              <td class="whitespace-nowrap py-4 pl-4 pr-3 text-sm font-medium text-gray-900 sm:pl-6">{{ task.id }}</td>
              <td class="whitespace-nowrap px-3 py-4 text-sm text-gray-900">
                {{ task.task_type }}
                <div v-if="task.parameters" class="text-xs text-gray-500 mt-1 truncate max-w-xs">{{ task.parameters }}</div>
              </td>
              <td class="whitespace-nowrap px-3 py-4 text-sm">
                <div class="flex flex-col gap-1">
                  <span :class="[
                    'inline-flex items-center rounded-md px-2 py-1 text-xs font-medium w-fit',
                    task.status === 'completed' ? 'bg-green-100 text-green-700' : 
                    task.status === 'running' ? 'bg-blue-100 text-blue-700 animate-pulse' : 'bg-red-100 text-red-700'
                  ]">
                    {{ task.status }}
                  </span>
                  <span class="text-xs text-gray-500" title="Started at">{{ new Date(task.created_at + (task.created_at.includes('Z') || task.created_at.includes('+') ? '' : 'Z')).toLocaleString() }}</span>
                  <span v-if="task.status === 'running' || task.completed_at" class="text-xs text-gray-500" title="Running Time">
                    ⏱️ {{ calculateRunningTime(task) }}
                  </span>
                </div>
              </td>
              <td class="px-3 py-4 text-sm text-gray-500">
                <div v-if="task.status === 'running'" class="flex flex-col gap-1">
                  <div class="flex justify-between text-xs mb-1">
                    <span>Found: {{ task.items_found }}</span>
                    <span>Saved: {{ task.items_saved }}</span>
                  </div>
                  <div v-if="task.progress_text" class="text-xs italic text-blue-600 truncate max-w-xs" :title="task.progress_text">
                    {{ task.progress_text }}
                  </div>
                  <div v-else class="text-xs italic text-gray-400">Processing...</div>
                </div>
                <div v-else class="text-xs text-gray-500">
                  Finished. Found: {{ task.items_found }}, Saved: {{ task.items_saved }}
                </div>
              </td>
              <td class="px-3 py-4 text-sm text-gray-500">
                {{ task.result_summary || '-' }}
              </td>
              <td class="relative whitespace-nowrap py-4 pl-3 pr-4 text-right text-sm font-medium sm:pr-6">
                <button v-if="task.status === 'running'" @click.stop="stopTask(task.id)" class="text-yellow-600 hover:text-yellow-900 mr-4">Stop</button>
                <button v-if="task.status === 'stopped' || task.status === 'error' || task.status === 'failed'" @click.stop="restartTask(task.id)" class="text-blue-600 hover:text-blue-900 mr-4">Restart</button>
                <button @click.stop="deleteTask(task.id)" class="text-red-600 hover:text-red-900">Delete</button>
              </td>
            </tr>
            <tr v-if="tasks.length === 0">
              <td colspan="6" class="px-3 py-8 text-center text-sm text-gray-500">No tasks found. Click "New Task" to start a scraper.</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Keywords Table -->
      <div v-if="currentTab === 'keywords'" class="bg-white shadow-sm ring-1 ring-gray-900/5 sm:rounded-xl overflow-hidden">
        <div v-if="loading" class="p-8 text-center text-gray-500">Loading data...</div>
        <table v-else class="min-w-full divide-y divide-gray-300">
          <thead class="bg-gray-50">
            <tr>
              <th scope="col" class="py-3.5 pl-4 pr-3 text-left text-sm font-semibold text-gray-900 sm:pl-6">Keyword</th>
              <th scope="col" class="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Source</th>
              <th scope="col" class="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Interval</th>
              <th scope="col" class="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Status</th>
              <th scope="col" class="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Last Run</th>
              <th scope="col" class="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Next Run</th>
              <th scope="col" class="relative py-3.5 pl-3 pr-4 sm:pr-6">
                <span class="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-200 bg-white">
            <tr v-for="kw in keywords" :key="kw.id" class="hover:bg-gray-50">
              <td class="whitespace-nowrap py-4 pl-4 pr-3 text-sm font-medium text-gray-900 sm:pl-6">{{ kw.word }}</td>
              <td class="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                <span :class="[
                  'inline-flex items-center rounded-md px-2 py-1 text-xs font-medium',
                  kw.source === 'manual' ? 'bg-purple-100 text-purple-700' : 
                  kw.source === 'ai_expanded' ? 'bg-indigo-100 text-indigo-700' : 'bg-yellow-100 text-yellow-700'
                ]">
                  {{ kw.source === 'ai_expanded' ? '✨ AI Expanded' : kw.source === 'scraped_from_store' ? '🌐 Scraped' : '✍️ Manual' }}
                </span>
              </td>
              <td class="whitespace-nowrap px-3 py-4 text-sm text-gray-500 capitalize">{{ kw.schedule_interval }}</td>
              <td class="whitespace-nowrap px-3 py-4 text-sm">
                <div class="flex items-center space-x-2">
                  <span :class="[
                    'inline-flex items-center rounded-md px-2 py-1 text-xs font-medium cursor-pointer',
                    kw.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'
                  ]" @click="toggleKeyword(kw.id)">
                    {{ kw.is_active ? 'Active' : 'Paused' }}
                  </span>
                  <span v-if="kw.current_status === 'running'" class="inline-flex items-center rounded-md px-2 py-1 text-xs font-medium bg-blue-100 text-blue-700 animate-pulse">
                    Running
                  </span>
                  <span v-else-if="kw.current_status === 'error'" class="inline-flex items-center rounded-md px-2 py-1 text-xs font-medium bg-red-100 text-red-700">
                    Error
                  </span>
                  <span v-else-if="kw.current_status === 'blocked'" class="inline-flex items-center rounded-md px-2 py-1 text-xs font-medium bg-orange-100 text-orange-800" title="Found many links but 0 valid Shopify stores. Blocked to save resources.">
                    Blocked
                  </span>
                </div>
              </td>
              <td class="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                {{ kw.last_run_at ? new Date(kw.last_run_at).toLocaleString() : 'Never' }}
              </td>
              <td class="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                {{ kw.next_run_at ? new Date(kw.next_run_at).toLocaleString() : '-' }}
              </td>
              <td class="relative whitespace-nowrap py-4 pl-3 pr-4 text-right text-sm font-medium sm:pr-6">
                <button @click="deleteKeyword(kw.id)" class="text-red-600 hover:text-red-900">Delete</button>
              </td>
            </tr>
            <tr v-if="keywords.length === 0">
              <td colspan="7" class="px-3 py-8 text-center text-sm text-gray-500">No automated keywords configured.</td>
            </tr>
          </tbody>
        </table>
      </div>

    </div>

    <!-- New Task Modal -->
    <div v-if="showTaskModal" class="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center">
      <div class="bg-white rounded-lg p-6 max-w-md w-full">
        <h3 class="text-lg font-medium text-gray-900 mb-4">Start New Scraper Task</h3>
        
        <div class="mb-4">
          <label class="block text-sm font-medium text-gray-700 mb-1">Task Type</label>
          <select v-model="newTaskType" class="w-full border-gray-300 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm border p-2">
            <option value="scrape_contacts">Extract Contacts (Process Pending URLs)</option>
            <option value="all_channels">All Channels (Search + FB + TikTok)</option>
            <option value="google_search">Automated Search (DuckDuckGo)</option>
            <option value="fb_ads">FB Ads Library Extraction</option>
            <option value="tiktok_ads">TikTok Ads Library Extraction</option>
          </select>
        </div>

        <div v-if="newTaskType !== 'scrape_contacts'" class="mb-4">
          <label class="block text-sm font-medium text-gray-700 mb-1">
            Keywords (comma separated)
          </label>
          <textarea v-model="newTaskParams" rows="3" class="w-full border-gray-300 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm border p-2" :placeholder="newTaskType === 'google_search' ? 'site:myshopify.com apparel, site:myshopify.com jewelry' : 'clothing brand, jewelry store'"></textarea>
          <div class="mt-2 flex justify-end">
            <button @click="generateKeywords" :disabled="generatingKeywords" class="inline-flex items-center px-3 py-1.5 border border-transparent text-xs font-medium rounded shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50">
              <span v-if="generatingKeywords">Generating...</span>
              <span v-else>✨ AI Expand Keywords</span>
            </button>
          </div>
        </div>
        
        <div v-if="newTaskType === 'fb_ads' || newTaskType === 'all_channels'" class="mb-4">
          <div class="flex space-x-4 mb-4">
            <div class="flex-1">
              <label class="block text-sm font-medium text-gray-700 mb-1">Country Code</label>
              <input type="text" v-model="fbCountry" class="w-full border-gray-300 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm border p-2" placeholder="e.g. US, UK, ALL">
            </div>
            <div class="flex-1">
              <label class="block text-sm font-medium text-gray-700 mb-1">Max Pages/Scrolls</label>
              <input type="number" v-model="fbMaxPages" min="1" max="10" class="w-full border-gray-300 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm border p-2">
            </div>
          </div>
          
          <label class="block text-sm font-medium text-gray-700 mb-1">
            Facebook Graph API Token (Optional)
          </label>
          <input type="text" v-model="fbApiToken" class="w-full border-gray-300 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm border p-2" placeholder="EAAG... (If empty, uses playwright fallback)">
          <p class="text-xs text-gray-500 mt-1">Provide a valid token with ads_read permission for fast API extraction.</p>
        </div>

        <div class="mt-5 sm:mt-6 flex space-x-3 justify-end">
          <button @click="showTaskModal = false" class="inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 sm:text-sm">
            Cancel
          </button>
          <button @click="submitTask" class="inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-indigo-600 text-base font-medium text-white hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 sm:text-sm">
            Start Task
          </button>
        </div>
      </div>
    </div>

    <!-- New Keyword Modal -->
    <div v-if="showKeywordModal" class="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center">
      <div class="bg-white rounded-lg p-6 max-w-md w-full">
        <h3 class="text-lg font-medium text-gray-900 mb-4">Add Automated Keyword</h3>
        
        <div class="mb-4">
          <label class="block text-sm font-medium text-gray-700 mb-1">Keywords (comma separated)</label>
          <textarea v-model="newKeywordWord" rows="3" class="w-full border-gray-300 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm border p-2" placeholder="e.g. fitness equipment, yoga mats"></textarea>
          <p class="text-xs text-gray-500 mt-1">These keywords will be periodically searched across all channels.</p>
        </div>

        <div class="mb-4">
          <label class="block text-sm font-medium text-gray-700 mb-1">Frequency</label>
          <select v-model="newKeywordInterval" class="w-full border-gray-300 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm border p-2">
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
            <option value="monthly">Monthly</option>
          </select>
        </div>

        <div class="mt-5 sm:mt-6 flex space-x-3 justify-end">
          <button @click="showKeywordModal = false" class="inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 sm:text-sm">
            Cancel
          </button>
          <button @click="addKeyword" class="inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-indigo-600 text-base font-medium text-white hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 sm:text-sm">
            Add Keyword
          </button>
        </div>
      </div>
    </div>
      
    <!-- Stats Tab -->
    <div v-if="currentTab === 'stats'" class="bg-white shadow overflow-hidden sm:rounded-lg">
        <div class="px-4 py-5 sm:px-6">
          <h3 class="text-lg leading-6 font-medium text-gray-900">Channel Performance</h3>
          <p class="mt-1 max-w-2xl text-sm text-gray-500">Distribution of acquired Shopify stores by source channel.</p>
        </div>
        <div class="border-t border-gray-200">
          <table class="min-w-full divide-y divide-gray-300">
            <thead class="bg-gray-50">
              <tr>
                <th scope="col" class="py-3.5 pl-4 pr-3 text-left text-sm font-semibold text-gray-900 sm:pl-6">Channel</th>
                <th scope="col" class="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Total Links Found</th>
                <th scope="col" class="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Shopify Stores Saved</th>
                <th scope="col" class="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Efficiency (%)</th>
                <th scope="col" class="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Avg Links / Keyword</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-200 bg-white">
              <tr v-for="(stat, index) in channelStats" :key="stat.channel || index">
                <td class="whitespace-nowrap py-4 pl-4 pr-3 text-sm font-medium text-gray-900 sm:pl-6 capitalize">
                  <span :class="{
                    'bg-blue-100 text-blue-800': stat.channel === 'fb_ads',
                    'bg-black text-white': stat.channel === 'tiktok_ads',
                    'bg-purple-100 text-purple-800': stat.channel === 'yahoo',
                    'bg-red-100 text-red-800': stat.channel === 'youtube',
                    'bg-green-100 text-green-800': stat.channel === 'trustpilot',
                    'bg-orange-100 text-orange-800': stat.channel === 'reddit',
                    'bg-yellow-100 text-yellow-800': stat.channel === 'google_shopping',
                    'bg-pink-100 text-pink-800': stat.channel === 'pinterest',
                    'bg-emerald-100 text-emerald-800': stat.channel === 'cps',
                    'bg-gray-100 text-gray-800': stat.channel === 'unknown' || !stat.channel
                  }" class="px-2.5 py-0.5 rounded-full text-xs font-medium">
                    {{ stat.channel ? String(stat.channel).replace('_', ' ') : 'Unknown' }}
                  </span>
                </td>
                <td class="whitespace-nowrap px-3 py-4 text-sm text-gray-500">{{ stat.links_found }}</td>
                <td class="whitespace-nowrap px-3 py-4 text-sm text-gray-500">{{ stat.stores_saved }}</td>
                <td class="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                  <div class="flex items-center">
                    <span class="mr-2">{{ stat.efficiency }}%</span>
                    <div class="w-full bg-gray-200 rounded-full h-1.5 max-w-[100px]">
                      <div class="bg-green-500 h-1.5 rounded-full" :style="{ width: `${stat.efficiency}%` }"></div>
                    </div>
                  </div>
                </td>
                <td class="whitespace-nowrap px-3 py-4 text-sm text-gray-500">{{ stat.avg_per_kw }}</td>
              </tr>
              <tr v-if="!channelStats || (Array.isArray(channelStats) && channelStats.length === 0)">
                <td colspan="5" class="whitespace-nowrap py-8 text-center text-sm text-gray-500">
                  No detailed channel metrics available yet. <br/> Run some keywords to start collecting data!
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
</template>
