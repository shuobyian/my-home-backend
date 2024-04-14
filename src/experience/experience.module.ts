import { Module, forwardRef } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { Experience } from 'src/experience/entities/experience.entity';
import { ExperienceController } from 'src/experience/experience.controller';
import { ExperienceService } from 'src/experience/experience.service';
import { ResultModule } from 'src/result/result.module';

@Module({
  imports: [
    TypeOrmModule.forFeature([Experience]),
    forwardRef(() => ResultModule),
  ],
  controllers: [ExperienceController],
  providers: [ExperienceService],
  exports: [ExperienceService],
})
export class ExperienceModule {}
