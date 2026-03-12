/**
 * TherapistKnowledgeBase.jsx
 * Add this component to your AdminPanel page
 * 
 * Import in AdminPanel.jsx:
 *   import TherapistKnowledgeBase from './TherapistKnowledgeBase'
 * 
 * Then add inside the admin panel JSX:
 *   <TherapistKnowledgeBase />
 */

import { useState, useEffect } from 'react'
import {
  getTherapistKnowledge,
  createTherapistKnowledge,
  updateTherapistKnowledge,
  deleteTherapistKnowledge
} from '../api/admin'

const CATEGORIES = [
  'CBT',
  'Anxiety',
  'Depression',
  'Grief',
  'Relationships',
  'Self-esteem',
  'Stress',
  'Trauma',
  'Addiction',
  'Anger Management',
  'Communication',
  'Coping Skills',
  'General'
]

export default function TherapistKnowledgeBase() {
  const [entries, setEntries] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [formData, setFormData] = useState({
    category: 'General',
    title: '',
    content: '',
    author: ''
  })
  const [saving, setSaving] = useState(false)
  const [filterCategory, setFilterCategory] = useState('all')

  useEffect(() => {
    loadEntries()
  }, [])

  const loadEntries = async () => {
    try {
      const data = await getTherapistKnowledge()
      setEntries(data.entries || [])
    } catch (err) {
      console.error('Failed to load:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async () => {
    if (!formData.title.trim() || !formData.content.trim()) return
    setSaving(true)
    try {
      if (editingId) {
        await updateTherapistKnowledge(editingId, formData)
      } else {
        await createTherapistKnowledge(formData)
      }
      resetForm()
      await loadEntries()
    } catch (err) {
      alert('Failed to save: ' + err.message)
    } finally {
      setSaving(false)
    }
  }

  const handleEdit = (entry) => {
    setFormData({
      category: entry.category,
      title: entry.title,
      content: entry.content,
      author: entry.author || ''
    })
    setEditingId(entry.id)
    setShowForm(true)
  }

  const handleDelete = async (id, title) => {
    if (!confirm(`Delete "${title}"?`)) return
    try {
      await deleteTherapistKnowledge(id)
      await loadEntries()
    } catch (err) {
      alert('Failed to delete: ' + err.message)
    }
  }

  const handleToggleActive = async (entry) => {
    try {
      await updateTherapistKnowledge(entry.id, { is_active: !entry.is_active })
      await loadEntries()
    } catch (err) {
      alert('Failed to toggle: ' + err.message)
    }
  }

  const resetForm = () => {
    setFormData({ category: 'General', title: '', content: '', author: '' })
    setEditingId(null)
    setShowForm(false)
  }

  const filteredEntries = filterCategory === 'all'
    ? entries
    : entries.filter(e => e.category === filterCategory)

  const usedCategories = [...new Set(entries.map(e => e.category))]

  return (
    <div className="glass-heavy" style={{ padding: '1.5rem', borderRadius: '0.75rem', marginBottom: '1.5rem' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
        <div>
          <h2 style={{ fontSize: '1.125rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.25rem' }}>
            Therapist Knowledge Base
          </h2>
          <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
            Professional therapeutic methods and techniques — injected into Wellness mode
          </p>
        </div>
        <button
          onClick={() => { resetForm(); setShowForm(!showForm) }}
          style={{
            padding: '0.5rem 1rem',
            background: showForm ? 'rgba(239,68,68,0.2)' : 'rgba(102,126,234,0.2)',
            border: `1px solid ${showForm ? 'rgba(239,68,68,0.3)' : 'rgba(102,126,234,0.3)'}`,
            borderRadius: '0.5rem',
            color: showForm ? '#ef4444' : '#667eea',
            cursor: 'pointer',
            fontSize: '0.875rem',
            fontWeight: 500
          }}
        >
          {showForm ? '✕ Cancel' : '+ Add Entry'}
        </button>
      </div>

      {/* Add/Edit Form */}
      {showForm && (
        <div style={{
          padding: '1.25rem',
          background: 'rgba(102,126,234,0.05)',
          border: '1px solid rgba(102,126,234,0.15)',
          borderRadius: '0.5rem',
          marginBottom: '1rem'
        }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginBottom: '0.75rem' }}>
            {/* Category */}
            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: '0.25rem' }}>
                Category
              </label>
              <select
                value={formData.category}
                onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                style={{
                  width: '100%',
                  padding: '0.5rem',
                  background: 'var(--bg-secondary, #1a1a3e)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: '0.375rem',
                  color: 'var(--text-primary)',
                  fontSize: '0.875rem'
                }}
              >
                {CATEGORIES.map(cat => (
                  <option key={cat} value={cat}>{cat}</option>
                ))}
              </select>
            </div>

            {/* Author */}
            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: '0.25rem' }}>
                Author / Therapist
              </label>
              <input
                type="text"
                value={formData.author}
                onChange={(e) => setFormData({ ...formData, author: e.target.value })}
                placeholder="e.g. Dr. Marija Petrović"
                style={{
                  width: '100%',
                  padding: '0.5rem',
                  background: 'var(--bg-secondary, #1a1a3e)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: '0.375rem',
                  color: 'var(--text-primary)',
                  fontSize: '0.875rem'
                }}
              />
            </div>
          </div>

          {/* Title */}
          <div style={{ marginBottom: '0.75rem' }}>
            <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: '0.25rem' }}>
              Title
            </label>
            <input
              type="text"
              value={formData.title}
              onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              placeholder="e.g. Cognitive Restructuring for Negative Thoughts"
              style={{
                width: '100%',
                padding: '0.5rem',
                background: 'var(--bg-secondary, #1a1a3e)',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: '0.375rem',
                color: 'var(--text-primary)',
                fontSize: '0.875rem'
              }}
            />
          </div>

          {/* Content */}
          <div style={{ marginBottom: '0.75rem' }}>
            <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: '0.25rem' }}>
              Therapeutic Method / Content
            </label>
            <textarea
              value={formData.content}
              onChange={(e) => setFormData({ ...formData, content: e.target.value })}
              placeholder="Describe the therapeutic technique, when to use it, and how to guide someone through it..."
              rows={6}
              style={{
                width: '100%',
                padding: '0.5rem',
                background: 'var(--bg-secondary, #1a1a3e)',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: '0.375rem',
                color: 'var(--text-primary)',
                fontSize: '0.875rem',
                resize: 'vertical',
                fontFamily: 'inherit'
              }}
            />
          </div>

          {/* Save Button */}
          <button
            onClick={handleSubmit}
            disabled={saving || !formData.title.trim() || !formData.content.trim()}
            style={{
              padding: '0.5rem 1.25rem',
              background: saving ? 'rgba(102,126,234,0.3)' : 'linear-gradient(135deg, #667eea, #764ba2)',
              border: 'none',
              borderRadius: '0.5rem',
              color: '#fff',
              cursor: saving ? 'not-allowed' : 'pointer',
              fontSize: '0.875rem',
              fontWeight: 500
            }}
          >
            {saving ? 'Saving...' : editingId ? 'Update Entry' : 'Add Entry'}
          </button>
        </div>
      )}

      {/* Filter */}
      {entries.length > 0 && (
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
          <button
            onClick={() => setFilterCategory('all')}
            style={{
              padding: '0.25rem 0.75rem',
              background: filterCategory === 'all' ? 'rgba(102,126,234,0.3)' : 'transparent',
              border: '1px solid rgba(102,126,234,0.2)',
              borderRadius: '1rem',
              color: filterCategory === 'all' ? '#667eea' : 'var(--text-secondary)',
              cursor: 'pointer',
              fontSize: '0.75rem'
            }}
          >
            All ({entries.length})
          </button>
          {usedCategories.map(cat => {
            const count = entries.filter(e => e.category === cat).length
            return (
              <button
                key={cat}
                onClick={() => setFilterCategory(cat)}
                style={{
                  padding: '0.25rem 0.75rem',
                  background: filterCategory === cat ? 'rgba(102,126,234,0.3)' : 'transparent',
                  border: '1px solid rgba(102,126,234,0.2)',
                  borderRadius: '1rem',
                  color: filterCategory === cat ? '#667eea' : 'var(--text-secondary)',
                  cursor: 'pointer',
                  fontSize: '0.75rem'
                }}
              >
                {cat} ({count})
              </button>
            )
          })}
        </div>
      )}

      {/* Entries List */}
      {loading ? (
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>Loading...</p>
      ) : filteredEntries.length === 0 ? (
        <div style={{
          padding: '2rem',
          textAlign: 'center',
          color: 'var(--text-secondary)',
          fontSize: '0.875rem',
          background: 'rgba(255,255,255,0.02)',
          borderRadius: '0.5rem',
          border: '1px dashed rgba(255,255,255,0.1)'
        }}>
          {entries.length === 0
            ? 'No therapeutic knowledge added yet. Click "+ Add Entry" to start.'
            : 'No entries in this category.'
          }
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          {filteredEntries.map(entry => (
            <div
              key={entry.id}
              style={{
                padding: '0.875rem',
                background: entry.is_active ? 'rgba(255,255,255,0.03)' : 'rgba(255,255,255,0.01)',
                border: '1px solid rgba(255,255,255,0.06)',
                borderRadius: '0.5rem',
                opacity: entry.is_active ? 1 : 0.5
              }}
            >
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '1rem' }}>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                    <span style={{
                      fontSize: '0.625rem',
                      padding: '0.125rem 0.5rem',
                      background: 'rgba(102,126,234,0.15)',
                      color: '#667eea',
                      borderRadius: '1rem',
                      fontWeight: 600,
                      textTransform: 'uppercase',
                      letterSpacing: '0.05em'
                    }}>
                      {entry.category}
                    </span>
                    {entry.author && (
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                        by {entry.author}
                      </span>
                    )}
                    {!entry.is_active && (
                      <span style={{
                        fontSize: '0.625rem',
                        padding: '0.125rem 0.375rem',
                        background: 'rgba(239,68,68,0.15)',
                        color: '#ef4444',
                        borderRadius: '0.25rem'
                      }}>
                        DISABLED
                      </span>
                    )}
                  </div>
                  <h3 style={{ fontSize: '0.9375rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.25rem' }}>
                    {entry.title}
                  </h3>
                  <p style={{
                    fontSize: '0.8125rem',
                    color: 'var(--text-secondary)',
                    lineHeight: 1.5,
                    whiteSpace: 'pre-wrap',
                    maxHeight: '4.5rem',
                    overflow: 'hidden'
                  }}>
                    {entry.content}
                  </p>
                </div>

                {/* Actions */}
                <div style={{ display: 'flex', gap: '0.375rem', flexShrink: 0 }}>
                  <button
                    onClick={() => handleToggleActive(entry)}
                    title={entry.is_active ? 'Disable' : 'Enable'}
                    style={{
                      padding: '0.375rem',
                      background: 'transparent',
                      border: '1px solid rgba(255,255,255,0.1)',
                      borderRadius: '0.25rem',
                      color: entry.is_active ? '#22c55e' : '#ef4444',
                      cursor: 'pointer',
                      fontSize: '0.875rem'
                    }}
                  >
                    {entry.is_active ? '●' : '○'}
                  </button>
                  <button
                    onClick={() => handleEdit(entry)}
                    title="Edit"
                    style={{
                      padding: '0.375rem',
                      background: 'transparent',
                      border: '1px solid rgba(255,255,255,0.1)',
                      borderRadius: '0.25rem',
                      color: 'var(--text-secondary)',
                      cursor: 'pointer',
                      fontSize: '0.875rem'
                    }}
                  >
                    ✎
                  </button>
                  <button
                    onClick={() => handleDelete(entry.id, entry.title)}
                    title="Delete"
                    style={{
                      padding: '0.375rem',
                      background: 'transparent',
                      border: '1px solid rgba(255,255,255,0.1)',
                      borderRadius: '0.25rem',
                      color: '#ef4444',
                      cursor: 'pointer',
                      fontSize: '0.875rem'
                    }}
                  >
                    ✕
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
