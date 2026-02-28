import axios from "axios";
import { google } from "googleapis";
import { config } from "../config/index.js";
import type { Lead, BookingRequest, BookingResult } from "../types/index.js";
import { createLogger } from "../utils/logger.js";

const logger = createLogger("appointment-setter");

/**
 * Appointment setter that integrates with Calendly and Google Calendar
 * to close the loop from conversation to booked meeting.
 */
export class AppointmentSetter {
  /**
   * Book a meeting via Calendly.
   * Generates a scheduling link and optionally auto-books a specific slot.
   */
  async bookViaCalendly(request: BookingRequest): Promise<BookingResult> {
    if (!config.booking.calendlyApiKey) {
      return { success: false, error: "Calendly API key not configured" };
    }

    try {
      // Create a single-use scheduling link for this specific lead
      const response = await axios.post(
        "https://api.calendly.com/scheduling_links",
        {
          max_event_count: 1,
          owner: config.booking.calendlyEventTypeUri,
          owner_type: "EventType",
        },
        {
          headers: {
            Authorization: `Bearer ${config.booking.calendlyApiKey}`,
            "Content-Type": "application/json",
          },
        }
      );

      const bookingUrl = response.data.resource.booking_url;

      logger.info(`Calendly link generated for ${request.leadName}`, {
        leadId: request.leadId,
        url: bookingUrl,
      });

      return {
        success: true,
        meetingUrl: bookingUrl,
      };
    } catch (error) {
      logger.error("Calendly booking failed", {
        leadId: request.leadId,
        error,
      });
      return {
        success: false,
        error: error instanceof Error ? error.message : "Calendly API error",
      };
    }
  }

  /**
   * Book directly on Google Calendar.
   * Creates an event and sends an invite to the lead.
   */
  async bookViaGoogleCalendar(
    request: BookingRequest,
    startTime: Date
  ): Promise<BookingResult> {
    if (!config.booking.googleCalendarCredentialsPath) {
      return { success: false, error: "Google Calendar credentials not configured" };
    }

    try {
      const auth = new google.auth.GoogleAuth({
        keyFile: config.booking.googleCalendarCredentialsPath,
        scopes: ["https://www.googleapis.com/auth/calendar.events"],
      });

      const calendar = google.calendar({ version: "v3", auth });

      const endTime = new Date(startTime);
      endTime.setMinutes(endTime.getMinutes() + request.duration);

      const event = await calendar.events.insert({
        calendarId: "primary",
        requestBody: {
          summary: `${request.meetingType === "discovery" ? "Discovery Call" : request.meetingType === "demo" ? "Product Demo" : "Consultation"} with ${request.leadName}`,
          description: request.notes,
          start: {
            dateTime: startTime.toISOString(),
            timeZone: "UTC",
          },
          end: {
            dateTime: endTime.toISOString(),
            timeZone: "UTC",
          },
          attendees: [{ email: request.leadEmail }],
          conferenceData: {
            createRequest: {
              requestId: request.leadId,
              conferenceSolutionKey: { type: "hangoutsMeet" },
            },
          },
          reminders: {
            useDefault: false,
            overrides: [
              { method: "email", minutes: 60 },
              { method: "popup", minutes: 15 },
            ],
          },
        },
        conferenceDataVersion: 1,
        sendUpdates: "all",
      });

      const meetingUrl =
        event.data.conferenceData?.entryPoints?.[0]?.uri ??
        event.data.htmlLink ??
        undefined;

      logger.info(`Google Calendar event created for ${request.leadName}`, {
        leadId: request.leadId,
        eventId: event.data.id,
        startTime: startTime.toISOString(),
      });

      return {
        success: true,
        meetingUrl,
        scheduledAt: startTime,
        calendarEventId: event.data.id ?? undefined,
      };
    } catch (error) {
      logger.error("Google Calendar booking failed", {
        leadId: request.leadId,
        error,
      });
      return {
        success: false,
        error:
          error instanceof Error ? error.message : "Google Calendar API error",
      };
    }
  }

  /**
   * Smart booking: tries Calendly first (lets lead pick their time),
   * falls back to Google Calendar direct booking.
   */
  async book(request: BookingRequest): Promise<BookingResult> {
    // Prefer Calendly (self-serve scheduling) for first interaction
    if (config.booking.calendlyApiKey) {
      const result = await this.bookViaCalendly(request);
      if (result.success) return result;
      logger.warn("Calendly failed, falling back to Google Calendar");
    }

    // Fallback to Google Calendar if preferred times are specified
    if (config.booking.googleCalendarCredentialsPath && request.preferredTimes?.length) {
      const startTime = new Date(request.preferredTimes[0]);
      return this.bookViaGoogleCalendar(request, startTime);
    }

    return {
      success: false,
      error: "No booking service configured. Set up Calendly or Google Calendar.",
    };
  }

  /**
   * Generate a booking CTA message to include in outreach.
   */
  async generateBookingCTA(lead: Lead): Promise<string> {
    if (config.booking.calendlyApiKey) {
      const result = await this.bookViaCalendly({
        leadId: lead.id,
        leadName: lead.fullName,
        leadEmail: lead.email ?? "",
        meetingType: "discovery",
        duration: 30,
        notes: `Discovery call with ${lead.fullName}, ${lead.title} at ${lead.company.name}`,
      });

      if (result.success && result.meetingUrl) {
        return `Here's a link to grab a time that works for you: ${result.meetingUrl}`;
      }
    }

    return "Would any of these times work for a quick 15-minute call this week?";
  }
}
