import { Controller, Get, Query } from '@nestjs/common';
import { ExperienceService } from 'src/experience/experience.service';

@Controller('experience')
export class ExperienceController {
  constructor(private readonly experienceService: ExperienceService) {}

  @Get()
  findAll() {
    return this.experienceService.findAll();
  }

  @Get('/walnut')
  walnut(
    @Query('presentLevel') presentLevel: number,
    @Query('presentExperience') presentExperience?: number,
    @Query('objectiveLevel') objectiveLevel?: number,
    @Query('productionPercent') productionPercent?: number,
  ) {
    return this.experienceService.walnut(
      presentLevel,
      presentExperience,
      objectiveLevel,
      productionPercent,
    );
  }
}
